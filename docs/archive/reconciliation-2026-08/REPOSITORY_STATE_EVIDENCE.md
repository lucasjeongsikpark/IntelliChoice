> **ARCHIVED 2026-08-20.** Point-in-time audit evidence (reconciliation, 2026-08-19/20) — **do not treat as current state.**
> **Current state:** `docs/PROJECT_STATE.md`
> **Reason:** Phase 3A repository-state evidence — the code readings behind the drift register, all at HEAD `344f016`. **Superseded by:** the 166-entry register at `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`.

# REPOSITORY_STATE_EVIDENCE.md — Phase 3A repository-observed-state verification

**Date:** 2026-08-19
**Phase:** 3A of the documentation-reconciliation audit — *documented intent vs observable repository state*.
**Scope:** repo-local evidence only. Every finding below was read out of this working tree
(`/Users/jeongsikpark/Downloads/Desktop-local/github_repo/IntelliChoice`) at HEAD `344f016`, its git
history, or its checked-in configuration. No live AWS, staging, GitHub, or LangSmith state was read;
no test was executed; no file outside `docs/reconciliation/` was modified.

This file is an **evidence register**, not a report. It records what each claim was verified against,
what could not be verified, and the adjudicated classification. Drift severities, decisions required,
and remediation belong to the Phase-3A findings documents, not here.

---

## 1. Method and evidence rules

Ten read-only inspector agents (W1–W9, with W6 split into W6a/W6b) were each assigned a disjoint set
of Phase-2 claims from §9 of `CLAIM_LEDGER.md`. Each inspector reported, per claim: intended state,
repository-observed state, file:line evidence, evidence type, verification limitations, and a
self-chosen classification. Classifications were then **adjudicated centrally**; where an
adjudication ruling names a claim, that ruling is the classification recorded here and the
inspector's own label is discarded. Inspector *evidence text* stands as written and is condensed
below without alteration of citations, quoted conditions, or counts.

### Conservative rules applied throughout 3A

1. **No test was executed.** Test files were read as source. Existence and assertion content can be
   confirmed; pass status cannot. Any claim whose truth depends on a test passing is capped at
   `TEST_EXISTS_NOT_EXECUTED` or carries that limitation explicitly.
2. **Terraform configuration is not deployed state.** No `terraform plan`, `apply`, `aws`, or `gh`
   command was run. A resource present in HCL is evidence about the configuration only; every
   deployed/live assertion is capped at `CONFIGURED_NOT_RUNTIME_VERIFIED` and deferred to Phase 3B.
3. **Presence of code is not verified runtime behaviour.** Wiring establishes reachability, not that
   a path executes as described under load, concurrency, or provider failure.
4. **`*.tfvars` existence is noted; content was never read.** `terraform/environments/staging/terraform.tfvars`
   exists and is gitignored (`.gitignore:55 *.tfvars`). Any conclusion resting on a variable *default*
   is contingent on that file not overriding it, and says so.
5. **Credential files and `.env` were never read.** The operative `.env` is out of scope; drift is
   recorded against `.env.example` only, and marked unresolvable in 3A where that matters (WORK-27).
6. **`../IntelliChoice-web` was never read.** Absence findings are scoped to this repository.
7. **Absence proven by grep is scoped to the pattern and file set used.** Each such block states the
   sweep's boundary. A feature under a different name would not surface.
8. **Git history was read read-only** (`git log`, `git show`, `git log -S`, `git status --short`).
   No mutating git command was run.

### Classification taxonomy (11 values)

| Value | Meaning |
|---|---|
| `CONFIRMED_IN_REPOSITORY` | The claim's asserted state is observable in the repository as described. |
| `PARTIALLY_IMPLEMENTED` | Some named halves/rows/items present, others absent or materially narrower. |
| `IMPLEMENTATION_DRIFT` | Code diverges from a documented contract and the code is the side that is wrong. |
| `DOCUMENTATION_DRIFT` | Code/config is right; a document asserts something the repository falsifies. |
| `CONFIGURED_NOT_RUNTIME_VERIFIED` | Configuration half fully confirmed; the deployed/live half is Phase 3B. |
| `TEST_EXISTS_NOT_EXECUTED` | The claim rests on a test that exists with the asserted content but was not run. |
| `NOT_IMPLEMENTED` | No implementing subject exists (may be correct, e.g. a dispositioned feature). |
| `UNVERIFIED` | 3A could not answer it; deferred to 3B or to external state. |
| `NOT_APPLICABLE_TO_REPOSITORY` | No repository evidence is owed for this claim. |
| `DEFERRED_BY_D152` | Frozen by D-152; not exercisable and currently not violated. |
| `CONFLICT` | Two live, mutually inconsistent statements of the same fact, neither retracted. |

`IMPLEMENTATION_DRIFT` was proposed once (SEC-03) and adjudicated down to `DOCUMENTATION_DRIFT`; it
therefore carries zero claims in the totals of §5.

---

## 2. Coverage against the Phase-2 verification queue

§9 of `CLAIM_LEDGER.md` partitions **231** claims (of 258) into five groups. The remaining **27**
claims carry `Evidence still required: none` and were already evidence-complete in Phase 2.

### 2.1 Group totals and 3A disposition

| §9 group | Items | Inspected in 3A | Deferred | Not covered in 3A |
|---|---|---|---|---|
| (a) code/test existence-and-pass checks | 129 | 129 | — | 0 |
| (b) terraform/AWS-state reads | 42 | 42 | — | 0 |
| (c) live/staging measurements | 14 | 2 | 12 → Phase 3B | 0 |
| (d) documentation-reconciliation decisions | 32 | 32 | — | 0 |
| (e) at-integration-time only | 14 | 0 | 14 → D-152 freeze | 0 |
| **§9 total** | **231** | **205** | **26** | **0** |
| Outside §9: evidence-complete claims re-inspected anyway | — | 1 (WORK-14) | — | — |
| **Evidence blocks in §3** | | **206** | | |

Two group-(c) items — **TEST-15** and **TEST-16** — turned out to be answerable inside 3A: §9 filed
them as re-measurements, but the instrument (ROADMAP's anchored `awk` at `ROADMAP.md:768-771`) runs
against `docs/AUDIT_FINDINGS.md` in this working tree, not against staging. W9 executed it read-only.
They are counted as inspected and are struck from the 3B list in §4.1.

### 2.2 Per-worker coverage

| Worker | Area | Claims | §9 groups covered |
|---|---|---|---|
| W1 | PII floor and data boundaries | 16 | (a) 16 |
| W2 | Learning core, grading, mastery, gain | 27 | (a) 27 |
| W3 | Gateway, structured output, cost accounting | 16 | (a) 16 |
| W4 | Terraform configuration (footprint, schedules, NAT, WAF/CloudTrail) | 24 | (b) 24 |
| W5 | Chat, RAG, refusals, location consent | 21 | (a) 21 |
| W6a | Graph/HITL, checkpoints, retention | 9 | (a) 9 |
| W6b | CI, ops, observability, alarms | 24 | (a) 6, (b) 18 |
| W7 | Frontends, e2e harness, user decisions | 12 | (a) 12 |
| W8 | Content pipeline, curriculum, question bank | 17 | (a) 16, + WORK-14 |
| W9 | Documentation lookups | 35 | (d) 32, (a) 1 (TEST-08), (c) 2 (TEST-15/16) |
| W10 | The five leftover group-(a) claims | 5 | (a) 5 |
| | **Total** | **206** | |

No claim was inspected by two workers; there are no duplicate blocks.

### 2.3 The five leftover group-(a) claims — closed by W10

These five were left unassigned by the first nine inspectors and were flagged here as 3A's one
coverage gap. **W10 closed the gap**: all five now carry repository evidence and a classification,
and their blocks sit at their family/ID sort positions in §3.

| Claim | §9 evidence line | 3A state |
|---|---|---|
| **ARCH-01** | code/infra covers the claimed session range | Inspected (W10) → `PARTIALLY_IMPLEMENTED` |
| **SEC-20** | no notice component; §6.1 track status | Inspected (W10) → `CONFIRMED_IN_REPOSITORY` |
| **TEST-04** | six structural sections' mechanisms exist | Inspected (W10) → `PARTIALLY_IMPLEMENTED` |
| **TEST-10** | notice component absent; §6.1 track started | Inspected (W10) → `CONFIRMED_IN_REPOSITORY` |
| **WORK-35** | consolidation job beside retention-purge | Inspected (W10) → `CONFIGURED_NOT_RUNTIME_VERIFIED` |

Accounting check: 129 inspected + 0 not covered = 129 group (a); 2 inspected + 12 deferred = 14
group (c); 42 + 32 + 14 complete the 231. Groups (a), (b) and (d) are now fully covered by 3A.

---

## 3. Evidence blocks

206 blocks, grouped by claim family, sorted by ID within family. Fields are fixed. "(adjudicated
centrally)" marks a classification the orchestrator assigned or changed against the inspector's own
label.

### 3.1 REQ family — 49 claims

#### REQ-01
- **Claim ID**: REQ-01
- **Domain**: product requirements
- **Intended state**: Postgres stores only `*_external_id` references; no names/emails/roles/relationships/attendance may appear in Postgres, logs, traces, or LLM payloads, with the org's MySQL as sole source of truth.
- **Repository-observed state**: All four named artifacts exist and match the claim's shape. 37 ORM tables; a grep of every `mapped_column` for PII-shaped names returns exactly three hits, all in `org_branches` (`address`, `phone`, `email`), plus `org_team_members.name` — these four are explicitly allowlisted in the purity test as org-published public website content (D-050). 35 `*_external_id` columns exist. Trace boundary has a `RedactingSpanExporter` wrapping both the production and the test exporter. Log boundary uses a templated `route.path` (query string dropped) plus a `PiiDenylistFilter` on top-level `extra` keys plus `redact_free_text` on `event`/`exc_info`. LLM boundary is 23 `*Payload` models, 17 under an exact field allowlist.
- **Evidence**: `packages/db/tests/test_schema_purity.py:17-53`; `packages/db/src/intellichoice_db/models/org.py:22-24`; `packages/observability/src/intellichoice_observability/tracing.py:72-89`; `packages/observability/src/intellichoice_observability/request_logging.py:76-77` "path = route.path if route is not None else UNMATCHED_PATH"; `packages/observability/src/intellichoice_observability/logging_config.py:9-14`; `scripts/scan_logs_pii.py:1-29`; `packages/shared/tests/test_bedrock_payload_pii_floor.py:202-240`
- **Evidence type**: code + test-source
- **Verification limitations**: No test run; nothing proves the running Postgres/CloudWatch/X-Ray stores are PII-free, only that the shapes and gates exist. Substring-shaped PII in free-text columns (`problem_reports`, `semantic_memory.fact_text`) is outside the exact-match denylist by design.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — from the inspector's PARTIALLY_IMPLEMENTED; the four PII-shaped columns are org-published public content under the documented D-050 exemption, not student PII, so the floor's intent holds)

#### REQ-02
- **Claim ID**: REQ-02
- **Domain**: deterministic-core guarantees
- **Intended state**: The PII floor is enforced at four distinct boundaries (Postgres schema, `extra="forbid"` LLM payloads, `RedactingSpanExporter` at trace export, access-log templating + log scanner), each with its own test, because a floor at one store does not transfer (D-104).
- **Repository-observed state**: All four boundaries and all four test files present. (1) `test_schema_purity.py` walks `Base.registry.mappers`. (2) `test_bedrock_payload_pii_floor.py` parametrizes 3 assertions over 17 models plus 2 completeness tests plus 6 hand-written constructor tests. (3) `test_tracing.py::test_sse_token_query_string_is_redacted_before_export` drives real `FastAPIInstrumentor`; its vacuity guard is at line 91 and its negative arm at line 100 — exactly the lines TRACEABILITY cites. (4) `scripts/scan_logs_pii.py` exists and `make scan-logs` is a real target.
- **Evidence**: `packages/observability/tests/test_tracing.py:91` "no span carried http.url - the assertion would be vacuous"; `:100-111`; `Makefile:248-250`; `packages/db/tests/test_schema_purity.py:56-66`; `packages/shared/tests/test_bedrock_payload_pii_floor.py:359-379`
- **Evidence type**: code + test-source + CI/build config (Makefile)
- **Verification limitations**: No test executed; `make scan-logs` requires live AWS credentials and was not run. Existence of four mechanisms is not evidence any of them currently pass.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-03
- **Claim ID**: REQ-03
- **Domain**: deterministic-core guarantees
- **Intended state**: The five named learning services contain no model/gateway call; LLMs confined to language tasks.
- **Repository-observed state**: Confirmed. None of the five imports `intellichoice_shared.bedrock`, a gateway, or any provider client. `grading.py` is pure comparison; `exam_policy.py` is static Pydantic config; `learning_gain.py` and `mastery_bootstrap.py` are arithmetic over repo rows; `study_plan.py` uses `random.Random` plus repository reads only. `authorization.py` is pure claims/adapter logic. No NL2SQL anywhere.
- **Evidence**: `apps/learning-api/src/learning_api/services/grading.py:1` "Deterministic multiple-choice grading (SPEC §5.9.3). No LLM is ever involved."; `:27` `return selected_option == correct_option`; `exam_policy.py:2`; `mastery_bootstrap.py:1` "Pure deterministic scoring - no LLM"; `study_plan.py:42-54`; negative grep for `bedrock|gateway|generate_structured|Anthropic` across the five files returns docstring prose only; `apps/learning-api/tests/test_exam_flow_determinism.py` exists
- **Evidence type**: code + negative grep + test-source (existence)
- **Verification limitations**: `test_exam_flow_determinism.py` not run. Absence of a model call in these five modules does not prove no LLM influences these outcomes via callers.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-04
- **Claim ID**: REQ-04
- **Domain**: deterministic-core guarantees
- **Intended state**: `selected_option == correct_option`, no LLM; stored record set fixed to eight named fields.
- **Repository-observed state**: Confirmed exactly. `grade()` is the literal comparison with `None` falling through to inequality. The persisted model carries all eight claimed fields plus `attempt_id` (PK) and `idempotency_key` (§5.9.2 dedup) — additions, not substitutions.
- **Evidence**: `grading.py:24-27` `def grade(selected_option: str | None, correct_option: str) -> bool: ... return selected_option == correct_option`; `grading.py:67-78`; `packages/db/src/intellichoice_db/models/assessment.py:110-127`
- **Evidence type**: code
- **Verification limitations**: No test executed. `selected_option` is nullable (S22 skipped-item synthesis), a documented widening of SPEC's field type.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-05
- **Claim ID**: REQ-05
- **Domain**: deterministic-core guarantees
- **Intended state**: A natural-language request never becomes SQL at runtime; structured output selects one of a fixed set of predefined, parameterized repository methods.
- **Repository-observed state**: Matches. Runtime chain is `scope_guard` → closed `ScopeAndIntentResponse.intent` → a fixed conditional-edge map (`build.py:41-58`, `_route_after_scope_guard`) → hand-written repository methods. Every query in `repositories/rag.py` is a SQLAlchemy `select()` with bound parameters; the only raw `text()` in chat-api/db runtime code is `pg_try_advisory_xact_lock` (`apps/chat-api/src/chat_api/routers/sessions.py:525`), `pg_advisory_xact_lock` (`rate_limit.py:44`, `cost_reservation.py:66`), `pg_notify` (`session_event_relay.py:189`) and the parameterized purge (`checkpoint_privacy.py:26-30`). No `QueryIntent` model exists anywhere — SPEC §5.26's name is unimplemented; the shipped equivalent is the intent enum.
- **Evidence**: `packages/db/src/intellichoice_db/repositories/assessment.py:200-203` ("SPEC §5.26.1 predefined method ... the parameterized-query shape the runtime must use instead of NL2SQL"); `apps/chat-api/tests/test_prompt_injection_eval.py:315-330`, docstring at `:316`; `packages/evals/src/intellichoice_evals/registry.py:108`; `CLAUDE.md:92`
- **Evidence type**: code + test-source
- **Verification limitations**: Only the two APIs' runtime paths were scanned. `apps/learning-api/src/learning_api/services/checkpoint_retention_cli.py:161` interpolates a table name into `text(f"DELETE FROM {table} ...")`, but the value is a code-side constant, not model output, and it is a CLI not a request path.
- **Classification**: CONFIRMED_IN_REPOSITORY (SPEC's `QueryIntent` name has no code counterpart — naming only, noted in limitations, no drift entry)

#### REQ-06
- **Claim ID**: REQ-06
- **Domain**: deterministic-core guarantees
- **Intended state**: SPEC §5.26.3 prescribes an internal NL2SQL pipeline (plan → allowlist → parser → read-only role → EXPLAIN → timeout → row limit) for dev/eval/analytics only.
- **Repository-observed state**: No ROADMAP or DECISIONS entry disposes of the internal variant at all. Corpus-wide `NL2SQL` grep returns 10 non-ledger hits, every one addressing only the *runtime* prohibition or the untestability of the SQL-parser item — none says the internal dev/eval/analytics variant is planned, dropped, or partially present. SPEC §5.26.3 carries no amendment or deferral marker.
- **Evidence**: `docs/SPEC.md:2641-2643` (§5.26.3, unmarked); `docs/ROADMAP.md:489`; `docs/DECISIONS.md:2104`, `:3031`, `:6806-6809`; `docs/TRACEABILITY.md:164-165`, `:567-574`; `CLAUDE.md:92`
- **Evidence type**: docs (negative)
- **Verification limitations**: Negative evidence (absence of a disposition); no source-tree inspection performed for a partial implementation.
- **Classification**: CONFIRMED_IN_REPOSITORY (the ledger's UNKNOWN status was right — the status is genuinely unstated)

#### REQ-07
- **Claim ID**: REQ-07
- **Domain**: deterministic-core guarantees
- **Intended state**: Role/branch/status/effective-window predicates applied in SQL before retrieval; parent-child links verified server-side; never prompt instructions.
- **Repository-observed state**: Confirmed. `repositories/rag.py:_apply_filters` (47-84) applies `RagChunk.status == "approved"` unconditionally, `audience.in_(audiences)`, the §5.21.3 branch rule (`branch_external_id IS NULL OR = :branch`, 61-71) and the effective window (79-82: `effective_from <= as_of` AND `effective_to IS NULL OR >= as_of`). Filters are built from resolved role/branch only, never query text. `scope_guard` deliberately does not receive `user_role`. Parent-child links verified server-side against MySQL. `user_role` is passed into the `RAG_ANSWER` payload as tone context *after* the SQL cut, not as the authorization mechanism.
- **Evidence**: `packages/db/src/intellichoice_db/repositories/rag.py:47-84`; `apps/chat-api/src/chat_api/services/role_access.py:127-145` ("never from the raw query text (that would let a prompt-injected document or a crafted question smuggle in an access-scope change)"); `apps/chat-api/src/chat_api/graph/nodes.py:471` "D-219: `user_role` deliberately not passed"; `apps/learning-api/src/learning_api/authorization.py:38-45`
- **Evidence type**: code
- **Verification limitations**: `test_rag_search.py` / `test_role_access.py` read as source only; not executed.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-08
- **Claim ID**: REQ-08
- **Domain**: deterministic-core guarantees
- **Intended state**: `academic_year = requested_year` deliberately not implemented (unified corpus), counted as dispositioned rather than traced.
- **Repository-observed state**: Matches, both halves quotable. `ChunkFilters.academic_year` at `rag.py:34-43`: "**Deliberately not set by the access-control path** (AUD-C-09, dispositioned 2026-08-03) ... the handbook set is unified rather than partitioned by year ... an unused option here is not an oversight to re-file." `role_access_filter`'s docstring: "**Five of §5.21.3's six predicates, by decision rather than omission** ... `academic_year = requested_year` is **not applicable to this corpus**". The returned `ChunkFilters` omits `academic_year`; the column/filter remains a working capability for ingestion queries (`_apply_filters` 76-77).
- **Evidence**: `packages/db/src/intellichoice_db/repositories/rag.py:34-43`, `:76-77`; `apps/chat-api/src/chat_api/services/role_access.py:132-138`, `:140-145`
- **Evidence type**: code
- **Verification limitations**: None material.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-09
- **Claim ID**: REQ-09
- **Domain**: failure handling
- **Intended state**: (observed-state claim) `resolve_target_student`'s read path returns the requested id unchecked for tutor/branch_manager; accepted risk expiring at first real traffic.
- **Repository-observed state**: Confirmed present and unchanged. The tutor/branch_manager branch has no scope check; writes 403, reads fall through returning the client-supplied id. `authorization.py:66-71`: `if access == "write": raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This role may not modify a student's records")` then `return requested_student_id`. In-code disposition at `:47-65` — "These two roles have no per-student scope check ... That is D-086's recorded, accepted risk since S33, and S43's `IcProfileAdapter` is what unblocks it; the formal disposition is scheduled for S46." 15 call sites all pass explicit `access=` (`students.py:160,315,366,429`; `sessions.py:1001,1040,1127,1234,1430,1676,1770,1866,1989,2121`; `stream.py:173,220`; `main.py:464`).
- **Evidence**: `apps/learning-api/src/learning_api/authorization.py:30-36`, `:38-45`, `:47-65`, `:66-71`; the 15 call sites above
- **Evidence type**: code
- **Verification limitations**: Whether "first real traffic" has begun is not determinable from the repository — no traffic or telemetry data is readable here. The write half's mitigation is code-present, not exercised.
- **Classification**: CONFIRMED_IN_REPOSITORY (the gap is present exactly as accepted; the write half is closed. The expiry condition itself remains unverified and is the shared G3/SEC-09 concern with SEC-09 and ARCH-18.)

#### REQ-10
- **Claim ID**: REQ-10
- **Domain**: HITL behavior
- **Intended state**: Explicit `interrupt()` approval before: attendance-verification email to branch manager, question to administrator, Google Calendar event, use of location, analysis of an uploaded solution image, and inclusion of potentially sensitive information in an email.
- **Repository-observed state**: **Five interrupt classes exist, not six.** Learning graph: `child_selection`, `email_approval` (attendance→branch manager). Chat graph: `email_approval` (admin escalation), `calendar_action`, `location_consent`. No image-analysis interrupt (`analyze_image` exists only as an unimplemented gateway method). No distinct gate for "potentially sensitive information in an email" — the nearest mechanisms are the email-preview payload inside the existing `email_approval` interrupt and unconditional PII redaction of free text before it reaches the node; neither is an interrupt keyed on sensitivity. The named router symbols exist at different lines than the ledger claims (`respond_to_interrupt` at 1819, not 1120; `_pending_task_interrupt` at 797, not 414). All three HITL test files exist.
- **Evidence**: `apps/learning-api/src/learning_api/routers/sessions.py:1819`, `:797`, `:770-776` ("a pending interrupt must be resolved via /respond before continuing"); `apps/learning-api/src/learning_api/graph/nodes.py:331`, `:460`; `apps/chat-api/src/chat_api/graph/nodes.py:793`, `:1019`, `:1134`; `packages/shared/src/intellichoice_shared/bedrock.py:5`; test files `apps/learning-api/tests/test_learning_graph_routes.py` (17 tests), `apps/chat-api/tests/test_calendar_action.py` (9), `apps/chat-api/tests/test_admin_escalation.py` (14)
- **Evidence type**: code + test-source (existence) + negative grep
- **Verification limitations**: Tests not executed. Code presence does not prove the interrupt fires in a deployed environment. Whether SPEC's six items were ever intended as six *separate* interrupt classes (vs two of them being properties of the email interrupt) is a SPEC-reading question 3A cannot settle from code, and 3B cannot resolve either.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — image analysis has no feature to gate, already dispositioned by D-078; the "sensitive info" half is a SPEC-interpretation item)

#### REQ-11
- **Claim ID**: REQ-11
- **Domain**: HITL behavior
- **Intended state**: The learning graph interrupts for parent multi-child selection and after *every* incorrect answer for hint/solution/video, both resumable through the same endpoint.
- **Repository-observed state**: Both interrupts exist and both resume through `POST /learning/sessions/{id}/respond` via an `interrupt_type`-discriminated union (`child_selection` / `email_approval` / `intervention_choice`). The intervention interrupt is **not** after every incorrect answer: routing requires `phase == "study"` AND `last_is_correct is False` AND `last_study_attempt_id is not None`, so an incorrect *final pre-exam* answer (which flips phase to `study` while still incorrect) deliberately does not interrupt. A hint below the ladder's final level self-loops back into a fresh `intervention_choice` interrupt.
- **Evidence**: `apps/learning-api/src/learning_api/graph/nodes.py:331`, `:1164`; `apps/learning-api/src/learning_api/graph/build.py:66-70`, `:74-82`; `apps/learning-api/src/learning_api/routers/sessions.py:354-373` (three `interrupt_type: Literal[...]` models unified as `RespondRequest = Annotated[..., Field(discriminator="interrupt_type")]`), `:1855` (resume rejected unless `pending.value.get("type") == body.interrupt_type`)
- **Evidence type**: code
- **Verification limitations**: No execution; the "every incorrect answer" scope difference is read from the routing predicate and its docstring, not observed at runtime.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — scope qualifier: the interrupt fires on study-phase incorrect answers with a recorded attempt, not literally every incorrect answer; the exclusion is deliberate and in-code)

#### REQ-12
- **Claim ID**: REQ-12
- **Domain**: failure handling
- **Intended state**: The attendance gate opens only on PRESENT; unknown/absent both block; MySQL unavailability must not imply present.
- **Repository-observed state**: Confirmed by construction — a single positive `if status == AttendanceStatus.PRESENT` early-return, everything else falls to the blocked path (no `else` to maintain). A MySQL exception in the caller returns `phase: "error"`, never a start.
- **Evidence**: `apps/learning-api/src/learning_api/services/attendance.py:105-127` (`if status == AttendanceStatus.PRESENT: return AttendanceGateResult(..., blocked=False ...)` then unconditional `create_blocked_session(...)` + `blocked=True`); `apps/learning-api/src/learning_api/graph/nodes.py:373-395` (`except Exception as exc: # SPEC §5.29: MySQL attendance failure -> block start`); `apps/learning-api/tests/test_auth_and_attendance.py:111` `def test_unknown_attendance_is_not_treated_as_present()` asserting `body["status"] == "unknown"` at `:120`
- **Evidence type**: code + test-source
- **Verification limitations**: Test not executed. TRACEABILITY.md cites `attendance.py:71-80` for `check_attendance_gate`; the function now begins at line 96 — a stale line citation, not a stale claim.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-13
- **Claim ID**: REQ-13
- **Domain**: product requirements
- **Intended state**: The UNKNOWN→blocked path is routine and must inform product work now; an Attendance Resolution path built and reachable.
- **Repository-observed state**: Built and reachable end to end. A distinct UNKNOWN message exists, separate from the absent message; a dedicated graph node and route resolve the block; a UI screen renders the choices; a parent-facing label map de-jargons `unknown`.
- **Evidence**: `attendance.py:34-50` `UNKNOWN_MESSAGE = ("Your attendance for this week has not been marked yet.\n\n" "This is normal - your Branch Manager may just not have recorded this week's class yet. ...")` with rationale at `:34-41` ("which D-152 §2 established is the *routine* production state, not a rare error"); selection at `:120` `message = UNKNOWN_MESSAGE if status == AttendanceStatus.UNKNOWN else BLOCKED_MESSAGE`; `graph/nodes.py:436 async def resolve_attendance(...)`; `routers/sessions.py:1108 resolve_attendance_choice` → `:1148 EntryInput(..., entry_action="resolve_attendance")`; `apps/learning-web/src/screens/AttendanceScreen.tsx`; `apps/learning-web/src/lib/attendanceLabels.ts:22` `unknown: "attendance not marked yet"`
- **Evidence type**: code (API, graph, UI)
- **Verification limitations**: Reachability inferred from wiring, not exercised. Production frequency of `attended = null` is not observable from this repo.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-14
- **Claim ID**: REQ-14
- **Domain**: failure handling
- **Intended state**: No answer from unapproved/expired/uncited sources; no result → refuse and offer escalation; conflict → surface and escalate.
- **Repository-observed state**: Confirmed. `apps/chat-api/src/chat_api/services/qa.py:311-313`: `if not verified or raw.confidence < confidence_threshold: return _no_answer(NO_SOURCE_MESSAGE, [])` — with `[]` citations deliberately (AUD-C-11); `:308-309` returns `CONFLICT_MESSAGE` on `raw.sources_conflict`. Zero chunks short-circuits at `:243`. Approved/effective enforcement is pre-retrieval (REQ-07/REQ-08). Refusal offers a human: `NO_APPROVED_SOURCE_MESSAGE` ("I can pass this on to a branch manager"), and `explain_access` sets `escalation_recommended: True`.
- **Evidence**: `apps/chat-api/src/chat_api/services/qa.py:243`, `:308-309`, `:311-313`; `apps/chat-api/src/chat_api/graph/nodes.py:667-673`; tests `apps/chat-api/tests/test_qa_service.py:665`, `:360-366`; `apps/chat-api/tests/test_prompt_injection_eval.py:251`
- **Evidence type**: code + test-source
- **Verification limitations**: Tests not executed. One narrow window: `synthesize_answer` re-fetches chunk bodies via `RagRepository.get_chunks_by_ids` (`repositories/rag.py:245-253`), which applies **no** status/effective predicates — it re-reads ids a filtered retrieval produced moments earlier in the same turn. Behavioural impact requires an approval/effective-window change inside one turn; not asserted anywhere.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-15
- **Claim ID**: REQ-15
- **Domain**: failure handling
- **Intended state**: With no reranker there are no scores, so the relevance floor is not applied; the degraded path emits `retrieval_rerank_degraded`.
- **Repository-observed state**: Exactly as claimed. `packages/knowledge/src/intellichoice_knowledge/retrieval.py:359-375`: on `BedrockGatewayError` it logs `logger.warning("retrieval_rerank_degraded", extra={reason, detail, candidate_count, cost_cents})` and returns `RetrievalResult(chunks=candidates[:top_k], ...)`; the `score > min_relevance_score` cut at `:387-390` is on the non-degraded path only. In-code comment: "Degraded, not failed ... it is unfiltered - the score>0 cut below never runs".
- **Evidence**: `packages/knowledge/src/intellichoice_knowledge/retrieval.py:340-392`; pinning test `packages/knowledge/tests/test_retrieval.py:381-405`
- **Evidence type**: code + test-source
- **Verification limitations**: "Alertable" is an infra property — the signal is a `logger.warning` with a stable message string and no accompanying metric counter; whether an alarm subscribes to it was not verified here.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-16
- **Claim ID**: REQ-16
- **Domain**: LLM behavior
- **Intended state**: All LLM output JSON-schema structured and Pydantic-validated; invalid output gets a *limited* retry then a deterministic fallback; invalid tool calls never executed.
- **Repository-observed state**: Implemented, with a stronger-than-claimed bound. `_validate_or_repair` (`packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:495-577`) validates once, permits **exactly one** repair call, then raises `StructuredOutputError("structured output still invalid after one repair retry")`. The truncation arm short-circuits before spending: `raise OutputTruncatedError(f"model hit max_output_tokens={max_output_tokens} before completing the {response_model.__name__} response; not retrying under the same ceiling")` with "A repair call here is pure waste: same prompt, same ceiling, same truncation... let the caller's fallback run (D-115)". The two dispositions are distinguished at the log boundary: `reason="output_truncated" if truncated else "schema_invalid"` (gateway.py:354). `_try_validate` (`:578+`) separates not-JSON (`NOT_JSON_DIGEST`) from valid-JSON-wrong-shape. Deterministic fallback at the caller: `_fallback_hint` / `_fallback_solution` in `apps/learning-api/src/learning_api/services/tutor.py:96,109`, invoked on `except BedrockGatewayError`.
- **Evidence**: gateway.py:354, 495-577, 578-594; tutor.py:96-153; tests `packages/adapters/tests/test_bedrock_gateway.py:114`, `:135`, `:237`, `:838`
- **Evidence type**: code + test-source
- **Verification limitations**: Tests read, never executed. The "invalid tool call is never executed" sub-clause was not separately verified — `tool_executor` is forwarded opaquely at gateway.py:307-310. That sub-clause stands UNVERIFIED.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-17
- **Claim ID**: REQ-17
- **Domain**: LLM behavior
- **Intended state**: A JSON-Schema/Pydantic model per each of thirteen artifact types, used at its boundary.
- **Repository-observed state**: **Eleven of thirteen** have a model and a non-mock production call site; two do not. Present and used: intent (`ScopeAndIntentResponse`, `LearningChatIntentResponse`), question template (`AuthoredGeneratedItemResponse`; note `GeneratedTemplateResponse` at bedrock.py:317 is now referenced only by `mock_provider.py`), hint (`HintResponse`), solution (`SolutionResponse`), tutor response (`TutorChatResponse`), parent report (`ReportInterpretationResponse`, `StageNarrativeResponse`), semantic-memory update (`MemoryUpdateResponse`), calendar event (`CalendarExtractionResponse`), RAG answer (`RagAnswerResponse`), citation (`Citation`; `LlmCitation` at bedrock.py:810 has no reference outside bedrock.py), evaluation result (`LlmJudgeResponse`). **Absent: topic mapping** — `BedrockTask.TOPIC_MAPPING` exists at bedrock.py:37 with no payload model, no response model, and no caller anywhere. **Absent: email draft** — no Pydantic LLM response model; the two email-draft paths (`learning_api/services/attendance.py:130 build_attendance_email_draft`, chat-api `state.email_draft`) are server-composed and deterministic.
- **Evidence**: `packages/shared/src/intellichoice_shared/bedrock.py` (class inventory L74-1378, task enum L30-72); repo-wide grep for `TOPIC_MAPPING` returning only the enum line and a docstring; per-model call-site grep across `packages/*/src` and `apps/*/src`
- **Evidence type**: code + negative grep
- **Verification limitations**: Boundary "use" established by import/reference, not by executing a call. Whether `GeneratedTemplateResponse`/`LlmCitation` are retained deliberately for the mock-provider contract was not resolved.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — the drift is doc-side: the missing topic-mapping model is dispositioned by D-024, `topic_resolver` being a deliberately deterministic non-LLM builder accepted 2026-07-16 at `DECISIONS.md:415`, and email drafts are server-composed by design per D-020; SPEC's thirteen-type list was never amended)

#### REQ-19
- **Claim ID**: REQ-19
- **Domain**: LLM behavior
- **Intended state**: Every paid call routes through `BedrockGateway` providing timeouts, bounded retry, max-token ceiling, per-session budget, circuit breaker, PII redaction, guardrails, model versioning, and a pre-flight `worst_case_cost_cents`.
- **Repository-observed state**: Method set matches the ledger's SUPERSEDED-in-part reading: the `BedrockGateway` Protocol (bedrock.py:1579-1602) declares exactly `generate_structured` and `create_embedding`. `ResilientBedrockGateway` implements timeout (`call_timeout_s=20.0`, gateway.py:88; per-call `timeout_s` override per D-233 at `:215`), bounded retry (`_max_retries`, loop at `:285`), output ceiling (`_HARD_MAX_OUTPUT_TOKENS = 4000` at `:78`, `capped_max_tokens = min(...)` at `:236`), per-session budget (`session_budget_cents=50.0` at `:93`, pre-call check `:244-263`), circuit breaker (`:110-134`), and `worst_case_cost_cents` (`:182-194`). Judge routing confirmed independently at `packages/evals/src/intellichoice_evals/llm_judge.py:64`. **Not found: guardrails.** Repo-wide case-insensitive grep for "guardrail" across `packages`, `apps`, `scripts` returns zero hits. Gateway-level PII redaction is also absent — redaction lives at callers.
- **Evidence**: bedrock.py:1-20, 1579-1602; gateway.py:78-194, 215-263, 285-310; llm_judge.py:64; the three named test files exist (`packages/adapters/tests/test_bedrock_gateway.py` 23 tests, `packages/db/tests/test_cost_reservation.py`, `apps/learning-api/tests/test_cost_reservation_estimates.py`)
- **Evidence type**: code + test-source + negative grep
- **Verification limitations**: Tests not executed. Not every paid-call site was enumerated, so "none bypasses the gateway" is unproven — only that the gateway exists with the listed features. A guardrail attached out-of-band (AWS console, or terraform outside this tree) would not appear.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — eight of ten listed features present; zero guardrail configuration exists repo-wide)

#### REQ-20
- **Claim ID**: REQ-20
- **Domain**: failure handling / spend-accounting
- **Intended state**: The named reconciliation test and script exist and pass; the `skipped_duplicate_id` gap is still open.
- **Repository-observed state**: Both artifacts exist. `test_a_slots_rows_account_for_every_cent_the_slot_reports` at `packages/curriculum/tests/test_authored_pipeline.py:2468` asserts three shapes — one accepted attempt (`rows[0].cost_cents == approx(outcome.cost_cents)` plus a non-vacuity guard `design.get("cost_cents", 0) > 0`), a repaired two-attempt slot (`len(designs) == 1`, `sum(r.cost_cents) == approx(outcome.cost_cents)`), and a rejected slot. `scripts/measure_spend_reconciliation.py` exists (5861 bytes), documented read-only with no model calls. Numeric inconsistency: the code says **31%** three times (script L7, L22, L111; test docstring L2471, L2475) while `docs/TRACEABILITY.md:241` and the ledger say **32.0%**; the script's own raw numbers (1278c/884c) compute to ~30.8%.
- **Evidence**: `packages/curriculum/tests/test_authored_pipeline.py:2468-2540`; `scripts/measure_spend_reconciliation.py:1-33`, `:111`; `docs/TRACEABILITY.md:241`
- **Evidence type**: test-source + code + docs
- **Verification limitations**: Neither the test nor the script was executed (both need a database), so pass status is unverified. The duplicate-id sub-claim is contradicted in part — see COST-06.
- **Classification**: TEST_EXISTS_NOT_EXECUTED (adjudicated centrally — both artifacts exist and match the D-294 story)

#### REQ-21
- **Claim ID**: REQ-21
- **Domain**: product requirements
- **Intended state**: Uploaded solution images deleted immediately after analysis; excluded from the RAG bucket, versioned S3, backups, and LangSmith traces (including Base64); lifecycle rule as a final safeguard only.
- **Repository-observed state**: **No subject for the requirement.** Zero source hits for `BlobStore`/`blob_store`, `MalwareScanner`/`malware`/`clamav`, `analyze_image`/`analyzeImage` (one prose mention), `solution_image`, `image_url`, `base64`. No `multipart`/`UploadFile`/`File(` upload endpoint anywhere in `apps/` or `packages/`. `apps/learning-api/src/learning_api/routers/` contains only `client_errors.py`, `parents.py`, `questions.py`, `sessions.py`, `stream.py`, `students.py`.
- **Evidence**: repo-wide negative greps as above; `packages/shared/src/intellichoice_shared/bedrock.py:5` is the only `analyze_image` occurrence and records absence ("none has a real caller yet (S18/S29 respectively; S29 was deferred, D-078)"); `packages/evals/src/intellichoice_evals/registry.py:74` "see D-078. No image-upload feature exists to emit this event."
- **Evidence type**: negative grep + code (prose confirming intentional absence)
- **Verification limitations**: Sweep confined to this repo; `../IntelliChoice-web` excluded by instruction, so a front-end upload widget cannot be ruled out from here. Backup and LangSmith trace contents are runtime facts, unverifiable statically.
- **Classification**: NOT_IMPLEMENTED (adjudicated centrally — correctly so; dispositioned by D-078, no implementing subject exists)

#### REQ-22
- **Claim ID**: REQ-22
- **Domain**: product requirements
- **Intended state**: S29 declined before any file was touched; the five named artifacts (`BlobStore`, `MalwareScanner`, `BedrockGateway.analyze_image`, upload router, executable math validator, `"image"` intervention choice) do not exist; S29 marked deferred-not-deleted.
- **Repository-observed state**: All five confirmed absent. The intervention choice enum is closed and contains no `image`: `apps/learning-api/src/learning_api/routers/sessions.py:368` — `choice: Literal["hint", "solution", "video", "continue"]`, and `:390` — `type: Literal["hint", "solution", "video"]`. `docs/ROADMAP.md:465` reads "### Session 29 — Multimodal solution images *(old S18, unchanged)* — **deferred, not built (D-078)**" — present, annotated, not deleted.
- **Evidence**: `apps/learning-api/src/learning_api/routers/sessions.py:364-390`; `docs/ROADMAP.md:11, 465, 491, 2173`; `packages/shared/src/intellichoice_shared/bedrock.py:5`; `packages/evals/src/intellichoice_evals/registry.py:74`
- **Evidence type**: negative grep + code (enum enumeration) + docs
- **Verification limitations**: `../IntelliChoice-web` not inspected. "Executable math validator" is ambiguous — `check_sympy_independent_solve` does exist but validates authored MC items, not image-extracted work; the phrase was read as scoped to the image path, which is absent.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-23
- **Claim ID**: REQ-23
- **Domain**: product requirements
- **Intended state**: D-078's incidental-capture privacy question must be resolved before §5.17 is built.
- **Repository-observed state**: Unresolved. `docs/OPEN_DECISIONS.md` contains no entry on image/photo privacy at all — its only `image` hits are container-image supply-chain items at `:15` and `:359-393`. DECISIONS' only incidental-capture text is D-078 itself. ROADMAP's §5.17 entry still says to revisit "once the privacy question, not just the architecture, has an answer."
- **Evidence**: `docs/DECISIONS.md:2033`, `:2045`; `docs/ROADMAP.md:471`; `docs/PROGRESS.md:14771`; `docs/OPEN_DECISIONS.md` (no matching entry)
- **Evidence type**: docs (negative)
- **Verification limitations**: Negative evidence; searched OPEN_DECISIONS / DECISIONS / ROADMAP / PROGRESS only.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-24
- **Claim ID**: REQ-24
- **Domain**: deterministic-core guarantees
- **Intended state**: Image analysis may only identify the incorrect step, improve hints, and extract misconception tags; the selected multiple-choice option determines the score.
- **Repository-observed state**: No image-analysis path exists (REQ-21/REQ-22), so the guarantee has no subject to violate. Scoring is driven solely by the selected option; no code reads any image artifact.
- **Evidence**: the same absence sweep as REQ-21; `apps/learning-api/src/learning_api/routers/sessions.py:368` (closed choice enum); `packages/shared/src/intellichoice_shared/bedrock.py:5`
- **Evidence type**: negative grep
- **Verification limitations**: Vacuous verification only — absence of the feature cannot demonstrate that a future implementation would honour the constraint.
- **Classification**: NOT_IMPLEMENTED (adjudicated centrally — vacuously satisfied; unfalsifiable while §5.17 is unbuilt. No drift.)

#### REQ-25
- **Claim ID**: REQ-25
- **Domain**: product requirements
- **Intended state**: A first-visit notice presenting eleven enumerated disclosures (SPEC §5.1.2); recorded CURRENT (unbuilt).
- **Repository-observed state**: No first-visit notice component exists in learning-web. `apps/learning-web/src/components/` holds ChatViz, ConnectingPanel, ErrorBoundary, ExamTimer, JourneyBar, QuestionFigure, QuestionNavBar, QuestionStem, ReportView, RichText, SkillFocus, SubmitConfirmationModal, TutorChatPanel; `apps/learning-web/src/screens/` holds 11 screens, none a notice/disclosure/consent screen. Case-insensitive grep for notice/disclosure/first-visit/firstVisit/consent across `apps/learning-web/src` returns only unrelated hits (`SubmitConfirmationModal.tsx`, `useFocusTrap.ts`, `stream.ts`, CSS).
- **Evidence**: `apps/learning-web/src/components/`, `apps/learning-web/src/screens/` (directory listings); negative grep over `apps/learning-web/src`
- **Evidence type**: negative grep
- **Verification limitations**: Absence-of-component only; no test or build run. SPEC §5.1.2's list was not re-read to check the eleven items are unamended.
- **Classification**: CONFIRMED_IN_REPOSITORY (absence as claimed)

#### REQ-26
- **Claim ID**: REQ-26
- **Domain**: product requirements
- **Intended state**: T-02 dispositioned, not built; `LocationConsentModal.tsx` is the pattern to follow.
- **Repository-observed state**: `apps/chat-web/src/screens/LocationConsentModal.tsx` exists — the only Consent/Notice/Disclosure-named file in either frontend. No counterpart in learning-web (REQ-25). `docs/TRACEABILITY.md:109` and `:650` state "dispositioned, not built — S45 builds it; the §6.1 track enumerates the eleven disclosures first", consistent with the source state.
- **Evidence**: `apps/chat-web/src/screens/LocationConsentModal.tsx`; `docs/TRACEABILITY.md:104-113`, `:650-652`; absence of any learning-web notice component
- **Evidence type**: code + docs
- **Verification limitations**: Whether S45 "has not run" and whether §6.1 has produced a list are documentation states not audited end to end (no session log read).
- **Classification**: CONFIRMED_IN_REPOSITORY (presence/absence as claimed)

#### REQ-27
- **Claim ID**: REQ-27
- **Domain**: product requirements
- **Intended state**: The learning app must verify `parental_consent_verified=true` before showing an age-appropriate student notice; the token must carry ten named claims.
- **Repository-observed state**: `TokenClaims` carries **exactly the ten claims named** — `sub`, `role`, `account_status`, `consent_status`, `parental_consent_verified`, `consent_version`, `student_age_band`, `issued_at`, `expires_at`, `audience` (no extras, no omissions). `parental_consent_verified` **is read** by `account_refusal_reason()` (auth.py:106), called from four app-level sites: `apps/learning-api/.../dependencies.py:122`, `apps/learning-api/.../routers/stream.py:162`, `apps/chat-api/.../dependencies.py:46`, `apps/chat-api/.../routers/stream.py:73`. The gate fails closed: `AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` is a deliberately **empty** frozenset, so today every student needs verified consent. No student-facing consent/privacy notice exists in either web app: grep for `parental|consent|under 13|guardian|age.appropriate` across both `src` trees returns only two unrelated code comments.
- **Evidence**: `packages/shared/src/intellichoice_shared/auth.py:26-36`, `:46-58`, `:99-108`; `apps/learning-api/src/learning_api/dependencies.py:122`; `apps/chat-api/src/chat_api/dependencies.py:46`; `docs/S42_DISCOVERY.md:260` "Tokens are HS256 `{id, iat, exp}`, 12 h, signed with a source-visible literal"
- **Evidence type**: code + docs + negative grep
- **Verification limitations**: Does not prove any real issuer mints the ten claims — the only issuer in-repo is `packages/adapters/.../fake_auth.py`. Does not prove the gate returns 403 at runtime. Absence of a notice is grep-based, not an exhaustive UI audit.
- **Classification**: PARTIALLY_IMPLEMENTED (enforcement half in code — ten claims exact, consent gate read at four sites, empty exempt set fails closed; notice half unbuilt (T-02, known); claims minted only by the dev fake, expected under D-152)

#### REQ-28
- **Claim ID**: REQ-28
- **Domain**: product requirements
- **Intended state**: Consent string shown first; geolocation only after permission; coordinates discarded after the Maps call; never in Postgres/MySQL/LangSmith/logs; ZIP/city/address alternative; raw manual address not retained.
- **Repository-observed state**: Mostly confirmed, two nuances. Notice copy is verbatim (`graph/nodes.py:218-221` vs `docs/SPEC.md:104-106`) and delivered through the `interrupt()` payload before any collection (`nodes.py:1134`). Browser geolocation only on explicit button press (`LocationConsentModal.tsx:31-66`). Coordinates never enter `QAState` — `graph/state.py` has **no** `ephemeral_location` field at all, and its docstring at `:4-6` still says the field is "not present — S15 adds them", stale prose since S15 shipped. Coordinates exist only inside the resume payload and inside `find_nearest_branches`, whose module docstring states "Precise coordinates never leave this function". MCP audit rows persist no arguments (`repositories/mcp.py:16-26`). `RespondBody` accepts `address`, which rides the same `__resume__` row and is removed by `purge_resume_writes` on the successful path only (see SEC-13). The UI offers ZIP and city, **not** an address field, though the API and `LOCATION_MISSING_MESSAGE` both mention address.
- **Evidence**: `apps/chat-api/src/chat_api/graph/nodes.py:218-221`, `:1134`; `docs/SPEC.md:104-106`; `apps/chat-web/src/screens/LocationConsentModal.tsx:31-66`, `:76`; `apps/chat-api/src/chat_api/graph/state.py:4-6`; `apps/chat-api/src/chat_api/services/branch_locator.py:64-115`; `packages/db/src/intellichoice_db/repositories/mcp.py:16-26`
- **Evidence type**: code
- **Verification limitations**: LangSmith trace contents are external; `traced_span("mcp.maps.geocode")` wraps the call but span attributes were not inspected beyond the call site.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — two LOW drifts: the consent modal offers ZIP/city but not address, and the `QAState` docstring's "S15 adds them" is stale in-code prose; the D-045 resume-value design is what shipped, which corroborates the REQ-52 adjudication)

#### REQ-29
- **Claim ID**: REQ-29
- **Domain**: product requirements
- **Intended state**: Among seven prohibited data uses, the tutor/manager summary path shares only scores and skill summaries and never transcripts.
- **Repository-observed state**: The verifiable clause holds. Audience field gating is a per-audience allowlist; the tutor set is six fields and `branch_manager` aliases it. No transcript field exists in the report payload at all, and there is no tutor/manager-facing route to expose one.
- **Evidence**: `apps/learning-api/src/learning_api/services/report.py:202-211` — `"tutor": {"pre_raw_score","post_raw_score","raw_gain","weak_skill_names","tutor_review_flagged","relevant_learning_facts"}` then `_AUDIENCE_FIELDS["branch_manager"] = _AUDIENCE_FIELDS["tutor"]`; comment `:199-201` "no usage/mastery/time detail, no chat/location/images (not present in this payload anyway)"; `:259` `allowed = _AUDIENCE_FIELDS[audience]`; repo-wide grep for `transcript` in learning-api returns three prose comments, no data path
- **Evidence type**: code + negative grep
- **Verification limitations**: Only one of the seven prohibitions was inspected (the one §9 names). The other six — data sale, ad targeting, marketing use, model training, facial-recognition retention, location history — were not audited.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — one of seven prohibitions inspected; that one holds. No drift.)

#### REQ-30
- **Claim ID**: REQ-30
- **Domain**: product requirements
- **Intended state**: Counsel review by U.S. education/child-privacy counsel is a mandatory production release gate.
- **Repository-observed state**: **No counsel-review record exists anywhere.** All six non-ledger `counsel` hits state the gate prospectively, never as performed. The gate *is* represented as a launch gate in ROADMAP's §6.1 parallel-track block, but **there is no launch-checklist document**; the only file self-describing as a launch-checklist item is `ENROLLMENT_FAQ_APPROVAL.md`, which claims to be "the only launch-checklist item gating the guest journey's canonical question" — a narrower scope that does not enumerate the counsel gate.
- **Evidence**: `docs/SPEC.md:57`; `docs/ROADMAP.md:2148-2150`; `docs/FIRST_VISIT_NOTICE.md:10`, `:236`; `docs/INCIDENT_RESPONSE.md:185`; `docs/ENROLLMENT_FAQ_APPROVAL.md:1`, `:82`, `:88`
- **Evidence type**: docs (negative)
- **Verification limitations**: Negative evidence for the review having occurred; an out-of-band counsel engagement would be invisible here.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-31
- **Claim ID**: REQ-31
- **Domain**: HITL behavior
- **Intended state**: Four escalating ladder steps; six persisted outcome labels exactly.
- **Repository-observed state**: Implemented as claimed, with one addition the code itself names: an interim seventh label `incorrect` for a wrong answer on a still-open skill line. The four steps map 1→retry, 2→retry with more-explicit-support recommendation, 3→prerequisite, 4+→exhausted/tutor-review.
- **Evidence**: `apps/learning-api/src/learning_api/services/study_outcomes.py` — `MAX_ATTEMPTS_PER_SKILL = 4`; `ladder_step()` branches `>= 4 → LadderStep("exhausted")`, `== 3 → LadderStep("prerequisite", EASIER_PREREQUISITE_MESSAGE)`, `== 2 → LadderStep("retry_same", MORE_EXPLICIT_SUPPORT_MESSAGE)`, else `LadderStep("retry_same")`; labels `INDEPENDENT_CORRECT ... UNRESOLVED` plus `INCORRECT = "incorrect"  # interim: wrong answer, skill line still open`; consumed at `services/flow.py:777,781,790,792`; `packages/db/src/intellichoice_db/models/mastery.py:106` `outcome_label: Mapped[str | None]` documented at `:70` as "one of the six §5.11.7"
- **Evidence type**: code
- **Verification limitations**: `outcome_label` is an unconstrained `String`, so the enum is enforced in Python only, not by the schema. No test executed.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — LOW drift: a documented interim seventh label exists beside the six terminal labels, in an unconstrained column)

#### REQ-32
- **Claim ID**: REQ-32
- **Domain**: LLM behavior
- **Intended state**: `HintResponse` carries `answer_revealed=false` alongside hint_text/concept_reminder/next_step_prompt/difficulty; guardrails configured; self-harm/abuse routed through a separately approved safety policy.
- **Repository-observed state**: (a) `HintResponse` exists at `bedrock.py:111` and carries `answer_revealed`; the deterministic fallback sets it explicitly (`answer_revealed=False`, tutor.py:104), and prompt-level answer-withholding rules exist (`_VIZ_RULE`: "never let the picture reveal the final answer"). (b) **Bedrock Guardrails: absent** — zero hits for "guardrail" (case-insensitive) across `packages`, `apps`, `scripts`, including `.tf`/`.yaml`/`.json`. (c) **Self-harm/abuse routing: present but keyword-based, not a separately approved safety policy.** `screen_for_safety_concern` (`apps/learning-api/src/learning_api/services/tutor_chat.py:161`) matches a fixed 10-item `_SAFETY_KEYWORDS` tuple ("kill myself", "suicide", "self-harm", "abuse", ...) and short-circuits to a fixed `SAFETY_RESPONSE`; called at `graph/nodes.py:1457` *before* intent classification, and the turn is persisted with `flagged_for_review=True`. One caller only — no equivalent screen in `apps/chat-api`. No approval artifact, policy document, or escalation destination beyond the boolean flag was found.
- **Evidence**: bedrock.py:111-120; tutor.py:96-107; tutor_chat.py:66-84, 161; graph/nodes.py:1457; `packages/db/src/intellichoice_db/models/tutor_chat.py:33-36`; test `apps/learning-api/tests/test_learning_chat.py:474`
- **Evidence type**: code + test-source + negative grep
- **Verification limitations**: A guardrail could be attached out-of-band (AWS console, or terraform outside this tree) — the absence is repo-scoped. Whether chat-api *should* carry a safety screen is not asserted anywhere read.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — MEDIUM drift on a minors platform: Guardrails absent, safety routing is a 10-keyword screen on the learning surface only, no approved safety-policy artifact)

#### REQ-33
- **Claim ID**: REQ-33
- **Domain**: deterministic-core guarantees
- **Intended state**: A correct answer after the full solution records `correct_after_solution` and never counts as independent mastery.
- **Repository-observed state**: Both halves present. Labeling uses most-revealing-first precedence, so solution outranks video and hint. Mastery grading gates on the label, and every mastery write goes through that path.
- **Evidence**: `study_outcomes.py` `correct_label()` — `if SOLUTION in support_history: return CORRECT_AFTER_SOLUTION` with docstring "once the solution has been shown, a later correct answer is `correct_after_solution` regardless of any hint also used earlier"; `counts_as_independent()` — `return label == INDEPENDENT_CORRECT`; `mastery_bootstrap.py:52-56` `_study_counts_as_correct`; applied in `resolve_graded_attempts` at `:82-85`; the only mastery writer is `flow._upsert_skill_mastery` (`flow.py:330-347`) fed from `_recompute_all_skill_mastery` (`:350`, called at `:799`, `:1029`)
- **Evidence type**: code (full call chain)
- **Verification limitations**: No test executed.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-34
- **Claim ID**: REQ-34
- **Domain**: failure handling
- **Intended state**: No runtime YouTube call; metadata filter then semantic search over a local pre-synced catalog; approved Khan Academy video only; explicit fallback offering hint or solution when none exists; sync failure keeps the last valid catalog.
- **Repository-observed state**: Confirmed on all four legs. (a) `apps/learning-api/src/learning_api/services/video_catalog.py` docstring: "a metadata filter (skill/difficulty, approved suitability) then a pgvector semantic rank, never a live YouTube call at learning time" and "no network call is ever made"; its only external call is `gateway.create_embedding`, the match coming from `repo.search_catalog(...)` over Postgres. (b) `YoutubeDataApiProvider` has exactly one importer, `packages/youtube/src/intellichoice_youtube/sync_cli.py:18,126` — the offline sync CLI; zero `googleapis`/YouTube-API hits under `apps/learning-api/src`. (c) `FALLBACK_MESSAGE` at `video_catalog.py:25-28` ("A verified video is not currently available for this skill. You may choose a hint or step-by-step solution instead."), returned when `has_servable_video(skill_id)` is False (`:64`) or on Bedrock/MCP failure. (d) `packages/youtube/src/intellichoice_youtube/catalog_sync.py:68-71` raises `YoutubeSyncError` on the fetch *before* any mutation; a budget cutoff also cannot look like a removal (`:86-90`).
- **Evidence**: files/lines above; `packages/db/src/intellichoice_db/repositories/youtube.py:122` (`has_servable_video`); `catalog_sync.py:76-84` (channel pin)
- **Evidence type**: code + import-graph analysis
- **Verification limitations**: "Approved Khan Academy video only" is enforced by `search_catalog`'s suitability filter and the sync-time channel pin; the filter's presence was read, not a live query result. No tests executed. Whether a *deployed* build matches this source is out of scope.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-35
- **Claim ID**: REQ-35
- **Domain**: deterministic-core guarantees
- **Intended state**: `base_problem_count = 5`; a seven-rule selection priority; no LLM.
- **Repository-observed state**: `BASE_PROBLEM_COUNT = 5` and no model call. All seven rules are addressed, but **rule 4's ranking is a deliberate, self-documented departure** from SPEC's order: when the recommended tier has no unused template, the code widens the tier rather than repeating a used one. The stored `base_problem_count` is `len(target_skill_ids)`, i.e. ≤5 when a topic has fewer stocked skills.
- **Evidence**: `study_plan.py:58` `BASE_PROBLEM_COUNT = 5`; module docstring `:3-34` enumerating rules 1-7; `:19-29` — "**This is a deliberate departure from SPEC's stated ranking, and the reason is measured.** ... On the dev database **57 of 201 study items did exactly that, 40 of them at the very first study item** ... One tier off is a worse question, the same question is a worse measurement, so the preference yields."; implementation `:145-158` and `:164-173`; `:296` `base_problem_count=len(target_skill_ids)`; `:253-260` D-288 stocked-skill filter
- **Evidence type**: code
- **Verification limitations**: The departure was read as recorded in the code docstring; `ROADMAP:2320` was not opened by the inspector to confirm it is the same departure recorded there. No test executed.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — the inversion is measured and matches ROADMAP:2320's recorded departure; SPEC §5.11.2 carries no amendment marker, so the code is right and the SPEC text is the stale side)

#### REQ-36
- **Claim ID**: REQ-36
- **Domain**: deterministic-core guarantees
- **Intended state**: Both gain formulas, the `not_applicable_pre_max` guard, and twelve persisted gain metrics.
- **Repository-observed state**: All three confirmed. Raw gain is `post_raw - pre_raw`. Normalized gain is `(post_raw - pre_raw) / (max_score - pre_raw)` where `max_score` is the *declared* item count, not the attempt count. The pre-max guard fires on `pre_raw >= max_score`. Exactly twelve of SPEC §5.13.3's metrics are persisted columns, plus `normalized_gain_status` and an extra diagnostic status value.
- **Evidence**: `apps/learning-api/src/learning_api/services/learning_gain.py:143` `raw_gain=post_raw - pre_raw`; `:105-109` (`if pre_raw >= max_score: normalized_gain = None; normalized_gain_status = "not_applicable_pre_max"`); `:103` `max_score = float(declared_item_count)` with AUD-L-08 rationale at `:96-102`; `:115-117` second status `"unmeasurable_out_of_range"` — "flag, never clamp"; twelve columns at `packages/db/src/intellichoice_db/models/mastery.py:165-177` matching `SPEC.md:1381-1393` one-for-one; `learning_gain.py:44-59`; test file `apps/learning-api/tests/test_learning_gain_bounds.py` exists
- **Evidence type**: code + docs cross-read + test-source (existence)
- **Verification limitations**: Test not executed. `hint_dependency` folds `correct_after_video` in with `correct_after_hint` (`:56-57`) — a defensible reading of §5.13.3, but a reading.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-37
- **Claim ID**: REQ-37
- **Domain**: product requirements
- **Intended state**: Post-exam matches on topic, skill, difficulty, template family, required reasoning steps, option construction; differs only in numeric parameters, option order, seed; no variant reuse; 2 questions at each of difficulties 1-5 per topic.
- **Repository-observed state**: `exam_policy.py` enforces **none** of this — 61 lines of per-session-type timer/navigation/hints/feedback config only (`:23-57`, whole field set = `session_type, time_limit_seconds, navigation, hints_allowed, feedback_visibility`). Parallel-form logic lives in `assessment_builder.build_post_exam`, which achieves all six matching dimensions structurally by reusing the pre-exam's `question_template_id` per slot and minting a new variant row per serving. Two departures are present and explicit in code: (a) authored templates repeat the pre-exam rendering with options permuted (D-189), (b) composition moved from "2 per tier 1-5" to "10 total" (D-302).
- **Evidence**: `exam_policy.py:23-57`; `assessment_builder.py:1-5`, `:215-231`, `:220-223` ("**except for a statically-rendered template, which has only the one rendering and therefore repeats it here by design (D-189)**"), `:37` `EXAM_QUESTION_COUNT = QUESTIONS_PER_DIFFICULTY * len(DIFFICULTIES)` with `:23-36` ("**Why the rule moved from '2 at every tier' to '10 in total.'**"), `:147-150`, `:154-162`; `variant_persistence.py:114-116` ("**This is where the post-exam's parallel form is partly given up** (D-189, the user's call)"), `:138-142`, `:159-166`
- **Evidence type**: code (three modules)
- **Verification limitations**: The six dimensions are satisfied *transitively* (same template ⇒ same skill/difficulty/reasoning-steps/option-construction), not by an explicit six-way check a test could falsify dimension by dimension. Whether the departure or the SPEC text is authoritative was not resolved by the inspector; `ROADMAP:1664` was not opened.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — two decided departures visible in code with no SPEC §5.13.1/.2 marker; plus a locus correction: enforcement lives in `assessment_builder`/`variant_persistence`, not `exam_policy.py`, so TRACEABILITY's and the ledger's locus is wrong)

#### REQ-38
- **Claim ID**: REQ-38
- **Domain**: product requirements
- **Intended state**: The assessment set is fixed once created; refresh/retry must not regenerate; `Idempotency-Key` header on the answers endpoint.
- **Repository-observed state**: Both present. `Idempotency-Key` is a **required** header (no default) on the answer route. A replayed topic-selection returns the existing items rather than rebuilding, and dedup is enforced at two layers: an idempotency-key lookup and a unique constraint on (session, variant).
- **Evidence**: `apps/learning-api/src/learning_api/routers/sessions.py:1227` `idempotency_key: Annotated[str, Header(alias="Idempotency-Key")]` (no `| None`, no default), threaded at `:1277,1293`; `graph/nodes.py:349-371` (`if flow.is_topic_selection_replay(...)` returns `get_items(...)`) with `:360-362`; `grading.py:61-65`; `models/assessment.py:102-108` `UniqueConstraint("assessment_session_id","question_variant_id", name="uq_assessment_attempts_session_variant")` with `:97-101` ("a changed answer rescored a 10-item exam as 10/11"); `grading.py:85-86` `raise ItemAlreadyAnsweredError(...)`
- **Evidence type**: code
- **Verification limitations**: "Regeneration impossible on refresh" verified for the topic-selection/replay path via `is_topic_selection_replay`; not every entry point that could reach `build_pre_exam` was enumerated. No test executed.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-39
- **Claim ID**: REQ-39
- **Domain**: product requirements
- **Intended state**: Bootstrap weights 1.0/1.4/1.9/2.5/3.2; no IRT path; the UI renders "Current estimated level".
- **Repository-observed state**: Weights exact; no IRT/Bayesian implementation exists anywhere (only docstring notes deferring it). **The UI wording is absent** — the string "Current estimated level" appears nowhere outside docs; the dashboard renders "Mastery by skill" and a bare `name="Mastery"` series.
- **Evidence**: `mastery_bootstrap.py:29` `DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.4, 3: 1.9, 4: 2.5, 5: 3.2}`, consumed at `:105-109`; `:3-4`; `packages/db/.../models/mastery.py:116`; case-insensitive grep for `irt|bayesian|item_response` over `apps/` + `packages/` yields only docstrings plus unrelated `item_responses` locals in `sessions.py:1532-1589`; grep for `"Current estimated level"` across the repo hits only `docs/SPEC.md:1111`, `docs/SPEC.md:1451` and the ledger — zero hits in `apps/learning-web/src` or `apps/chat-web/src`; grep for `estimated` in `apps/learning-web/src` returns nothing; `apps/learning-web/src/screens/StudentDashboardScreen.tsx:532` `<h2>Mastery by skill</h2>`, `:544`, `:571` `name="Mastery"`
- **Evidence type**: code + exhaustive negative grep across both web apps
- **Verification limitations**: The search was for the literal SPEC phrase and for "estimated"; a semantically equivalent but differently worded hedge elsewhere in the UI would not have matched.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — weights and no-IRT confirmed; the SPEC-required UI wording appears nowhere in either frontend and no disposition exists, which weakens Phase-2 REQ-39's CURRENT status for the UI half)

#### REQ-40
- **Claim ID**: REQ-40
- **Domain**: product requirements
- **Intended state**: The two named leak tests exist and assert leak-cleanliness.
- **Repository-observed state**: Both files exist and assert what the claim implies. `test_leak_sample.py` (14 lines) asserts a golden sweep returns no unexpected leaks and pins a D-079 negative-integer regression case. `test_mock_hint_is_leak_clean.py` asserts the mock's personalization introduces no answer the canonical text did not, never trips the leak-phrase check, and still names the misconception while varying by level.
- **Evidence**: `packages/evals/tests/test_leak_sample.py:4-13` — `assert sweep_for_unexpected_leaks() == []` and `test_negative_integer_leak_case_is_present()` asserting `case.expect_leak is True` / `case.correct_answer_text == "-4"` with comment "a leading '-' used to defeat the old `\b`-anchored check entirely"; `packages/curriculum/tests/test_mock_hint_is_leak_clean.py:78,105`, `:113,119`, `:122,134-135`
- **Evidence type**: test-source
- **Verification limitations**: Not executed — the claim's confidence rests on these passing. Neither test covers the dashboard raw-skill-id violation the ledger's "contradicts" note describes (AUDIT_2026_08_16 §3, 30/33 topics); that fix was not audited here.
- **Classification**: TEST_EXISTS_NOT_EXECUTED (adjudicated centrally — both leak tests exist with correct assertions)

#### REQ-41
- **Claim ID**: REQ-41
- **Domain**: deterministic-core guarantees
- **Intended state**: Every multiple-choice item passes the SPEC §5.8.5 check list before use, implemented with Python/SymPy/custom evaluators.
- **Repository-observed state**: `validate_authored_item` (`packages/curriculum/src/intellichoice_curriculum/authored_validation.py:1862-1901`) runs eleven named checks. Diffed against `SPEC.md:928-940`, which lists **eleven** bullets and states no count: implemented are exactly-one-correct-answer (`:1489`), unique options (`:221`), correct option matches executable solution (`:1420` + `route_answer` `:746` + `check_hint_solution_answer_agreement` `:1642`), no answer leakage (`:1611`, `:1510`, `:1553`), complete question wording (partial proxy — `check_schema_and_markdown_safety` `:199-219`), age-appropriate wording (`:1705`, whose own comment at `:129-131` calls it "a rough proxy only; real nuance is the LLM judge's job"). **No implementing deterministic check, or materially narrower:** (1) no division-by-zero check (only incidental `bound.is_finite`/NaN handling at `:1144-1149`; grep for `zoo`/`ZeroDivision`/`division by zero` across `packages/curriculum/src` returns nothing); (2) no numeric-value-range check on the item's values — the only range check is metadata (`:1684-1690`, difficulty 1-5 and `estimated_time_seconds > 0`); (3) difficulty-rubric compliance is only that range check, the substance being the LLM judge (`ai_pipeline.py:1970`); (4) duplicate detection is absent from the gate, living one layer up (`ai_pipeline.py:1821` exact text, `:1834` cross-topic skeleton, `:816` cosine at `NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD = 0.05` whose comment calls the threshold "a placeholder pending real-embedding calibration"); (5) topic/skill alignment is deterministically only *structural* (`pipeline_cli.py:443`, `ai_pipeline.py:1581-1588`), semantic alignment being the LLM reviewer. Six checks exist that SPEC does not list.
- **Evidence**: `authored_validation.py:199-1901` (function list at `:1862-1901`); `ai_pipeline.py:811-816, 1581-1588, 1810-1840, 1948-1988`; `pipeline_cli.py:414-449`; `docs/SPEC.md:926-944`
- **Evidence type**: code (function-by-function diff)
- **Verification limitations**: "No implementing check" judged by absence of code that could enforce the bullet; a check enforced implicitly by a stricter neighbour (e.g. SymPy raising on a zero denominator inside `_sympify`) would make division-by-zero incidentally caught rather than checked — not resolvable by reading alone. No tests executed.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — four of eleven bullets have no deterministic implementing check inside the gate and two named checks are materially narrower; the ledger's "twelve" is an overcount against SPEC's eleven. Weakens Phase-2 REQ-41 as written.)

#### REQ-42
- **Claim ID**: REQ-42
- **Domain**: LLM behavior
- **Intended state**: The LLM difficulty label is a bootstrap label, to be superseded by observed evidence including success after hints.
- **Repository-observed state**: **No recalibration from observed response data exists.** Repo-wide grep for `recalibrat` returns only documentation (`docs/SPEC.md:914` "As production data accumulates, recalibrate using:", `docs/TRACEABILITY.md:329`, `docs/PROGRESS.md:11015`) — zero code hits. Grep for `success_rate`, `p_value`, `observed difficulty`, `item_difficulty` across non-test source returns nothing. `difficulty_label` is read-only outside the authoring pipeline (`study_plan.py:94-156, 212`; `graph/nodes.py:878, 894`; `sessions.py:1545`; `mastery_bootstrap.py:89`). The only re-labelling is generation-time and judge-driven (retier tests at `test_authored_pipeline.py:2937, 3084`). `docs/TRACEABILITY.md:329-332` states the position: "§5.8.4's recalibration is future work by SPEC's own wording ('as production data accumulates'), and there is no production data... Not a gap; a requirement whose trigger condition has not occurred."
- **Evidence**: greps above; `docs/TRACEABILITY.md:329-332`; `docs/SPEC.md:914`; the read-only usages listed
- **Evidence type**: negative grep + code (read/write analysis) + docs
- **Verification limitations**: Verified that no *code* recalibrates; whether any gating decision depends on the label alone is behavioural — the label does feed selection via `_closest_to_recommended`'s tier preference, which is question routing rather than a pass/fail gate, and not every consumer was traced. Within the authoring pipeline the judge label *is* final for the persisted tier.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — on the correct reading: no recalibration code exists AND SPEC's own trigger has not occurred; `TRACEABILITY:329-332` dispositions it. LOW wording tension only.)

#### REQ-43
- **Claim ID**: REQ-43
- **Domain**: LLM behavior
- **Intended state**: A closed enum of **nine** `TurnReason` values, carried on every turn; wording is not the contract.
- **Repository-observed state**: The enum is closed and every answer-writing node sets it, but it holds **ten** values, not nine. `apps/chat-api/src/chat_api/services/outcomes.py:27-65`: `ANSWER`, `NO_APPROVED_SOURCE`, `SOURCES_CONFLICT`, `ACCESS_REQUIRED`, `OUT_OF_SCOPE`, `HUMAN_ACTION_REQUIRED`, `POLICY_RESTRICTED`, `SYSTEM_ERROR`, `NEEDS_CLARIFICATION`, plus `CANCELLED = "cancelled"` (added by D-402, documented at `:59-65` as "Deliberately last and outside the 'worked -> did not work' ordering"). `docs/SPEC.md:1988-1998`'s table still lists exactly nine rows with no `cancelled`. All fifteen `"answer":` writes in `graph/nodes.py` are accompanied by a `reason` (`:404, :426, :454, :555, :668, :687, :772, :866, :971, :998, :1063, :1151, :1167, :1185`), and `resolve_role` clears `"reason": None` per turn (`:328-332`). `chat-web/src/types.ts:67` exposes `reason?: string | null` — a bare string, not the union.
- **Evidence**: outcomes.py:27-65; SPEC.md:1980-2008; the reason writes above; types.ts:67
- **Evidence type**: code + docs
- **Verification limitations**: The ledger cites SPEC §5.19.5 at 1929-1955 and §5.19.4 at 1898-1927; on this HEAD they are at 1980-2008 and 1951-1979 (≈+53 lines) — ledger line anchors are stale.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — the code is correct; SPEC §5.19.5's nine-row table omits `CANCELLED`, a client-visible reason. This weakens Phase-2 REQ-43's "nine-value taxonomy" as written. Secondary LOW: `types.ts` does not narrow `reason` to the union.)

#### REQ-44
- **Claim ID**: REQ-44
- **Domain**: LLM behavior
- **Intended state**: The no-reason-code-restated check is applied over the whole message set, not the one message that was wrong.
- **Repository-observed state**: The test exists and iterates a set rather than a single case: `apps/chat-api/tests/test_turn_reasons.py:46-55` loops `for reason, message in REASON_MESSAGES.items()` and asserts `reason.value.replace("_", " ") not in message.lower()`. The set it covers is `REASON_MESSAGES` — five entries (`outcomes.py:134-140`: no_approved_source, sources_conflict, access_required, out_of_scope, system_error). Other user-facing strings (`UNAVAILABLE_INTENT_MESSAGES`, `LOCATION_*`, `RATE_LIMITED_MESSAGE`, calendar copy) are not in that dict and so are not swept, though the docstring's promise is "the next message added is covered by construction" — true only for messages added to `REASON_MESSAGES`.
- **Evidence**: `apps/chat-api/tests/test_turn_reasons.py:46-55`; `apps/chat-api/src/chat_api/services/outcomes.py:134-140`; the node message constants
- **Evidence type**: test-source
- **Verification limitations**: Cannot confirm the test "can fail for the right reason" without executing it; the assertion is a plain substring check, which would pass vacuously for any reason whose copy is defined outside `REASON_MESSAGES`.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — LOW drift: the sweep covers 5 of 10 reasons; node-local user-facing copy is outside it)

#### REQ-45
- **Claim ID**: REQ-45
- **Domain**: LLM behavior
- **Intended state**: `access_required` copy names no role and no document; the tier is selected server-side, kept in state and logged, never returned.
- **Repository-observed state**: Confirmed on all three legs. `outcomes.py:93-96` `ACCESS_REQUIRED_MESSAGE` = "I can't answer that from the sources available to you. Some information is only available once you sign in, so signing in may help." — no role, no document; an 18-line comment above it (`:75-92`) records the measured (D-351: 1-in-8) and structural reasons. Logged not returned: `graph/nodes.py:679-683` `logger.info("access_hint_offered", extra={"required_role": hint.required_role, "user_role": state.user_role})`, then `:684-692` returns `answer: ACCESS_REQUIRED_MESSAGE` with `access_hint` carrying `required_role` in **state**; the boundary model drops it — `AccessHintResponse` has `message` only, constructed field-by-field at `sessions.py:928`. Pinned by `tests/test_turn_reasons.py:72-92` and `:250-277` (asserting `set(AccessHintResponse.model_fields) == {"message"}`).
- **Evidence**: outcomes.py:75-96; graph/nodes.py:679-692; routers/sessions.py:139-..., :928; tests/test_turn_reasons.py:72-92, :250-277
- **Evidence type**: code + test-source
- **Verification limitations**: The old role-specific strings remain live in `role_access.ACCESS_HINT_MESSAGES` (`:21-29`) as the probe's selector; a test guards against them being re-wired to `answer`, but they are one edit from user-facing again.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-47
- **Claim ID**: REQ-47
- **Domain**: LLM behavior
- **Intended state**: The shipped final out-of-scope line matches the amended SPEC string exactly; the eight supported topics are unchanged; donations are still out of scope.
- **Repository-observed state**: Matches. `docs/SPEC.md:1966-1971` reads: "I can help with IntelliChoice programs, branches, schedules, volunteering, / student learning, parent information and tutor or branch procedures. / I can't help with that topic through this assistant. For anything else, your branch / can point you to the right person." Code (`outcomes.py:70-73` + `:109-113`) composes exactly that text; the only differences are SPEC's hard line wraps inside sentences. The amendment note is present and dated at `SPEC.md:1973-1979`; the topic list at `SPEC.md:1953-1962` is eight items with no donations entry. Pinned by `tests/test_turn_reasons.py:58-69` (asserts "unrelated" and "general-purpose" absent) and `:107-118`.
- **Evidence**: `docs/SPEC.md:1951-1979` vs `apps/chat-api/src/chat_api/services/outcomes.py:70-113` (both read and diffed); tests/test_turn_reasons.py:58-69, :107-118
- **Evidence type**: docs + code + test-source
- **Verification limitations**: The ledger and task brief cite SPEC:1914-1918 / 1898-1927 for this block; on this HEAD it is at 1951-1979. Comparison was done against the located text, not the cited line numbers. Line-anchor discrepancies across readers are a LOW note, not drift — `git status` shows no doc changed.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-48
- **Claim ID**: REQ-48
- **Domain**: failure handling
- **Intended state**: `system_error` denotes our failure, not a statement about the question; the next step is retry.
- **Repository-observed state**: Confirmed. `outcomes.py:125-129` `SYSTEM_ERROR_MESSAGE` = "I can't look that up right now - the assistant is temporarily unavailable.\n\nThis is a problem on our side, not with your question. Please try again in a few minutes. If it keeps happening, contact your branch manager." No corpus claim, explicit disclaimer, retry offered. The enum member's comment (`:53-55`) states "Explicitly *not* a statement about the question (AUD-C-07/AUD-C-08...)". `graph/nodes.py:74` aliases `SERVICE_UNAVAILABLE_MESSAGE = qa.SERVICE_UNAVAILABLE_MESSAGE`, so one string serves all degraded paths; `_reason_for_qa_answer` (`nodes.py:501-516`) maps it back to `SYSTEM_ERROR` by identity rather than re-classifying. Pinned by `tests/test_turn_reasons.py:137-157`.
- **Evidence**: outcomes.py:53-55, :125-129; graph/nodes.py:74, :501-516; services/qa.py:34-region; tests/test_turn_reasons.py:137-157
- **Evidence type**: code + test-source
- **Verification limitations**: None material; tests not executed.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### REQ-49
- **Claim ID**: REQ-49
- **Domain**: failure handling
- **Intended state**: §5.29's nineteen named failures each have an implementation and a test; the common mechanisms include a dead-letter queue and a smaller-model fallback.
- **Repository-observed state**: Four rows sampled. (i) **Static concept-hint fallback on hint failure — PRESENT**: `_fallback_hint` (tutor.py:96) returns a deterministic `HintResponse` with a skill/topic-templated `concept_reminder`; `generate_hint` catches `BedrockGatewayError` and returns it plus `exc.cost_cents` (`:150-153`). (ii) **Dead-letter queue — ABSENT**: zero hits for `dead.letter`, `dead_letter`, or `DLQ` across `packages`, `apps`, `scripts` (`.py`/`.tf`/`.yaml`). (iii) **Smaller-model fallback on Bedrock timeout — ABSENT**: zero hits for `fallback_model`, `smaller_model`, "smaller model", "fallback model"; the gateway's timeout path is bounded retry against the *same* `model_id` (gateway.py:285-310), then `_record_failure()` → circuit open. (iv) **LangSmith/metrics failure non-blocking — PRESENT**: `request_logging.py:105-120` uses `except Exception` around the access-log emit with an explicit D-393 comment; `metrics.py:157-164` mirrors it; `scheduled_jobs.py:64` carries `except Exception:  # noqa: BLE001 - see the docstring; reporting must not fail the job`; a `langsmith_ingest_failed` alarm is routed in `packages/observability/tests/test_alarm_severity_routing.py:31`.
- **Evidence**: tutor.py:96-153; gateway.py:285-320; request_logging.py:105-120; metrics.py:157-164; scheduled_jobs.py:64; negative greps for DLQ and model fallback
- **Evidence type**: code + negative grep
- **Verification limitations**: Four of nineteen rows sampled; the other fifteen (MySQL profile/attendance, Postgres writer, VLM, etc.) were not inspected. Absences are repo-scoped greps on keyword vocabulary — a DLQ implemented under a different name (e.g. a retry table) would not be caught.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — MEDIUM: two of §5.29's named common mechanisms are absent repo-wide; the static concept-hint fallback and non-blocking telemetry are present)

#### REQ-51
- **Claim ID**: REQ-51
- **Domain**: deterministic-core guarantees
- **Intended state**: Each of the sixteen §5.5.2 components is implemented at its declared node type.
- **Repository-observed state**: The four "deterministic" components and the LLM-agent component match: Learning Orchestrator = LangGraph `StateGraph` (`graph/build.py:100`); Attendance Gate (`attendance.py:96`); Grading Node (`grading.py:24`); Learning Gain Service; Mastery Estimator (`mastery_bootstrap.py:1`); Study Planner; Tutor Agent (`tutor.py:142,208,299` `gateway.generate_structured`); Parent Report Agent (`report.py:487`); Intervention Router (`build.py:_route_after_submit_answer`); Video Catalog Tool; Memory Consolidator. **Mismatch 1 — Topic Resolver declared "Structured LLM", implemented deterministic**, self-dispositioned at `services/topic_resolver.py:3-9` ("This is a deterministic (non-LLM) resolver ... SPEC §5.25.2's 'Topic mapping | Reliable structured output' row implies an eventual LLM-based resolver ... that variant isn't built until then"); grep confirms no `generate_structured` in the module. **Mismatch 2 — Tutor Summary Generator declared "Structured service"** but produced by the same LLM report path as the parent report, differing only by audience field allowlist (`report.py:487-496` reached for every audience, `:202-211` gating fields, `:515` logging audience; grounding-check and deterministic fallback at `:497-517`). Not separately located: Attendance Escalation Agent ("Tool agent") is a deterministic template plus an MCP `gmail.send_email` call (`attendance.py:130-187`); Assessment Manager ("Subgraph") has no `add_subgraph` — the eight nodes in `build.py:100-117` are flat. The closing rule holds: "Grading, attendance, authorization, and score calculation remain deterministic" (`SPEC.md:531`).
- **Evidence**: as cited inline above; SPEC table read at `docs/SPEC.md:493-531`
- **Evidence type**: code + negative grep + docs
- **Verification limitations**: "Structured service", "Tool agent" and "Subgraph" are not precisely defined types, so three of the four findings turn on a reading of ambiguous vocabulary rather than a clear contradiction. No tests executed.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — escalation answered: treat those labels as descriptive, falsifiable only where the label implies LLM-vs-deterministic. On that reading two substantive mismatches stand (Topic Resolver, Tutor Summary Generator); one DOCUMENTATION_DRIFT entry covers the §5.5.2 table's stale rows, and the deterministic-core closing rule itself HOLDS.)

#### REQ-52
- **Claim ID**: REQ-52
- **Domain**: deterministic-core guarantees
- **Intended state**: `LearningState` enumerates ~40 fields, all identity references being `*_external_id`, names/emails never in graph state; `QAState` carries `ephemeral_location` rather than persisted coordinates.
- **Repository-observed state**: `LearningState` is a single `BaseModel` with **32** top-level fields — not ~40 (SPEC) and not 31 (U7's correction). Identity fields are `user_external_id`, `student_external_id`, `parent_external_id`, `candidate_children: list[str]`; no name-, email- or coordinate-shaped field exists. `QAState` **does not carry `ephemeral_location`** at all — its own docstring says `location_consent`/`ephemeral_location` "are still not present - S15 adds them", and grep finds the identifier only in that comment. `QAState` identity fields are `user_external_id`/`branch_external_id`; `email_draft` is typed `EmailDraftState` (subject/body, no recipient).
- **Evidence**: `apps/learning-api/src/learning_api/graph/state.py:13-125` (32 fields); `apps/chat-api/src/chat_api/graph/state.py:4-7`, `:23-29`
- **Evidence type**: code
- **Verification limitations**: Field-name inspection only; does not prove no PII travels inside a `dict`-typed field (`last_items`, `last_intervention`, `pending_*` are untyped `dict`/`list[dict]`, outside any name-based check). **LangGraph checkpoint tables are not ORM models, so `test_schema_purity.py` does not cover checkpointed state at all** — a real limitation of the whole PII-floor posture, carried forward.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — three-way field-count drift (32 code / ~40 SPEC / 31 U7); `QAState.ephemeral_location`'s absence matches D-045's design, so the CODE is right and both SPEC §5.19.3 and the stale in-code comment are documentation drift)

### 3.2 ARCH family — 35 claims

#### ARCH-01
- **Claim ID**: ARCH-01
- **Domain**: architecture
- **Intended state**: `docs/ARCHITECTURE.md` documents the system as built through **S0–S34 plus the S36–S43 audit/stabilization work and the §2.6 launch gate**, explicitly as a map of "what exists now" rather than the target design.
- **Repository-observed state**: The scope statement is present verbatim at `docs/ARCHITECTURE.md:3-13`, including "This file is a map of *what exists now*, not the full target design" and "Session provenance is tagged in each node (e.g. `(S6)`)". **Code/infra for the claimed range exists**, spot-verified per named block: S8 gateway `packages/shared/src/intellichoice_shared/bedrock.py`; S9/S20–S23 `packages/curriculum/src/intellichoice_curriculum/{authored_bank,adjudications}.py` plus `apps/learning-api/src/learning_api/services/{exam_policy,grading,hint_personalization_scheduler}.py`; S11/S16 `apps/learning-web`, `apps/chat-web`; S12–S13 `packages/knowledge/src/intellichoice_knowledge/{ingest,retrieval,reembed}.py`; S14–S15 `packages/shared/src/intellichoice_shared/mcp.py` plus the four `fake_*` adapters; S24–S28 `packages/memory` and `services/{report,stage_narrative}.py`; S30 `packages/evals/...{llm_judge,qa_coverage,registry}.py`; S31 `packages/observability/`; S32–S35 `terraform/environments/staging/` and `.github/workflows/deploy-staging.yml`. S29 is absent, consistent with the file's own "not built" list. **The scope statement is stale in the "up to" direction**: the same file documents work well past S43 — `:1106-1107` (D-404/D-405), `:1119` (D-409), `:1147` (D-416), `:1163` (D-421), `:1177` (D-423), `:2072` (`chat_escalation_sends`, D-421); 15 lines match `D-4xx|W2x|U7`, and `docs/PROGRESS.md:9-11` records "MILESTONE 15 IS CLOSED — six sessions, seven PRs ... (2026-08-18, D-416 → D-423 ... W22–W27)". **Session-provenance tagging is uneven** against the `:3-13` claim: `grep -oE "\(S[0-9]+\)"` yields `(S1)…(S22) (S24)…(S29) (S34) (S37) (S39) (S48)` — no tags for S23, S30–S33, S35, S36, S38, S40–S43, i.e. exactly the deployment/audit range the header claims to cover, and no tag scheme at all for the W-milestones. The cross-doc conflict is confirmed: `docs/FINAL_ARCHITECTURE.md:3-12` still says ARCHITECTURE.md documents "*what exists now* (through S31, S29 deferred)". The file self-flags this rot class at `:49-54`.
- **Evidence**: `docs/ARCHITECTURE.md:3-13`, `:19-23`, `:26-36`, `:49-54`, `:1106-1107`, `:1119`, `:1147`, `:1163`, `:1177`, `:2072`; `docs/FINAL_ARCHITECTURE.md:3-12`; `docs/PROGRESS.md:9-11`; `packages/` and `apps/` listings. Commands: `git log --format=... -- docs/ARCHITECTURE.md`, `grep -oE "\(S[0-9]+\)" docs/ARCHITECTURE.md | sort -u`, `grep -nE "D-4[0-9][0-9]" docs/ARCHITECTURE.md`
- **Evidence type**: docs + code (artifact presence) + git history
- **Verification limitations**: "Covers the claimed session range" was checked by artifact presence per named subsystem, not by a per-session diff of every S0–S43 deliverable; no tests run; the deployed topology — the other half of §5.3's artifact — is 3B.
- **Classification**: PARTIALLY_IMPLEMENTED (as an observed-state claim: the claimed range is present in code/infra, but the file's declared scope no longer matches its own contents. Drift MEDIUM, cross-linked to the ARCH-26 FINAL_ARCHITECTURE entry, whose "through S31" is the same rot in the opposite direction.)

#### ARCH-02
- **Claim ID**: ARCH-02
- **Domain**: deployment
- **Intended state**: `terraform/environments/` should contain staging only; no production environment; no real `go.intellichoice.org` integration.
- **Repository-observed state**: Confirmed at config level. `terraform/environments/` has exactly one child directory, `staging/`. No `production/` or `dev/` directory, and no `aws_organizations_*` resource anywhere in `terraform/`.
- **Evidence**: `ls terraform/environments/` → `staging` only; `terraform/environments/staging/main.tf:358` — "STAGING ONLY. `terraform/environments/production` (S48) must never define these" (a forward reference to a directory that does not exist)
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; whether staging is *live* and whether any prod account exists is Phase 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — config half confirmed exactly: staging is the only environment defined)

#### ARCH-03
- **Claim ID**: ARCH-03
- **Domain**: deployment
- **Intended state**: No independent auth or consent capture exists; `/dev/token` is the only authenticated path until S44.
- **Repository-observed state**: Confirmed at code/config level. `/dev/token` is registered in both apps (`apps/learning-api/src/learning_api/main.py:484`, chat-api equivalent) and is the only token-issuing route. No auth provider exists anywhere: `grep -riE 'cognito|oidc|oauth|saml|auth0|okta|clerk|firebase_auth'` over `terraform/**.tf` returns **only GitHub Actions deploy OIDC** (`terraform/modules/iam/main.tf:129-190`, `create_github_oidc_provider`), and the same grep over `apps/*/src` + `packages/*/src` returns **zero hits**. The frontend still has a dev-login screen.
- **Evidence**: `apps/learning-api/src/learning_api/main.py:346-367,484-527`; `packages/shared/src/intellichoice_shared/auth.py:111-177`; `terraform/modules/iam/main.tf:129-190`; `apps/chat-web/src/api/client.ts:72-88`
- **Evidence type**: code + terraform config + negative grep
- **Verification limitations**: "The deployed apps still issue dev tokens" is a live assertion; only image/config content is verifiable here. The **absence-of-auth half is repo-provable by exhaustive negative grep** and is not merely configuration.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally)

#### ARCH-04
- **Claim ID**: ARCH-04
- **Domain**: operational
- **Intended state**: Four EventBridge schedules — `session-consolidate` 18:00, `chat-purge` 18:10, `retention-purge` 18:50, `memory-consolidate` Sundays 18:30, UTC.
- **Repository-observed state**: **Confirmed exactly.** `terraform/modules/scheduled-jobs/main.tf` defines FIVE jobs in `locals.jobs`, four with `enabled = true`: `session-consolidate` `cron(0 18 * * ? *)` (`:52`, enabled `:60`); `chat-purge` `cron(10 18 * * ? *)` (`:65`, `:72`); `memory-consolidate` `cron(30 18 ? * SUN *)` (`:91`, `:105`); `retention-purge` `cron(50 18 * * ? *)` (`:80`, `:87`); `youtube-sync` `cron(0 19 ? * SUN *)` (`:108`) with `enabled = var.youtube_sync_enabled` (`:125`), default `false`. Timezone `schedule_expression_timezone = "UTC"` (`:196`); state `= var.enabled && each.value.enabled ? "ENABLED" : "DISABLED"` (`:198`), module `var.enabled` default `true`. Resource type is `aws_scheduler_schedule` (EventBridge **Scheduler**), not `aws_cloudwatch_event_rule` with a cron — the module header states that choice. The only `aws_cloudwatch_event_rule` is `ops_task_failed` (`:241`), an event-pattern rule for non-zero ops-task exits.
- **Evidence**: `terraform/modules/scheduled-jobs/main.tf:8-11, 52-125, 196-198, 241`; `terraform/modules/scheduled-jobs/variables.tf:63-77`; `terraform/environments/staging/main.tf:842-866`
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; whether the four have fired unattended for ≥1 week is Phase 3B. `var.enabled` / `var.youtube_sync_enabled` could be overridden by the unread `terraform.tfvars`.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — config half confirmed exactly, including cron expressions and UTC. LOW drift: the module header at `:13-20` still says "**Four jobs are defined, three are enabled**" and predates `session-consolidate`; five are defined and four enabled.)

#### ARCH-05
- **Claim ID**: ARCH-05
- **Domain**: operational
- **Intended state**: The nightly order is load-bearing; `checkpoint_retention_cli` is the job deliberately left unscheduled until `session-consolidate` has a record of firing.
- **Repository-observed state**: Confirmed, and the ambiguous referent is **resolved by config**: `checkpoint_retention_cli` has **no** schedule — it appears nowhere in terraform (only `Makefile:106` and its own module). The four scheduled commands are `session_consolidation_cli`, `tutor_chat_purge_cli`, `retention_purge_cli`, `intellichoice_memory.consolidate_cli`. `retention-purge` (the AUD-L-04/D-114 row-purge job) IS scheduled and enabled; the *checkpoint* retention job is not. So ARCHITECTURE.md L28's "retention-purge" and L35-36's "that retention job stays unscheduled" refer to two different jobs, and both statements are true.
- **Evidence**: `terraform/modules/scheduled-jobs/main.tf:41-51` ("That job is deliberately unscheduled today; scheduling it before this one would be actively unsafe, which is why this lands first and alone"), `:53`, `:66`, `:81`, `:92`; `grep checkpoint_retention_cli terraform/` → no hits
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; the invariant's code half (eligibility read from `learning_sessions`, chat-by-absence classification) was another worker's scope (WORK-19/WORK-21).
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the ARCHITECTURE.md ambiguity is RESOLVED: two different jobs, both doc statements true; LOW doc-clarity note only)

#### ARCH-06
- **Claim ID**: ARCH-06
- **Domain**: operational
- **Intended state**: (per the losing text) `memory-consolidate` "manual trigger only", `chat-purge` "no scheduler yet".
- **Repository-observed state**: **Falsified by config.** Both jobs have enabled `aws_scheduler_schedule` resources: `chat-purge` `cron(10 18 * * ? *)` enabled (`modules/scheduled-jobs/main.tf:65,72`), `memory-consolidate` `cron(30 18 ? * SUN *)` enabled (`:91,105`). The module's opening comment records the prior state ARCHITECTURE.md:1850/2068 describes: "Before this existed, `aws events list-rules` and `aws scheduler list-schedules` were both empty and all four jobs were `make` targets a human ran (AUD-F-06)" (`:3-6`).
- **Evidence**: `terraform/modules/scheduled-jobs/main.tf:3-6, 65, 72, 91, 105`; `docs/ARCHITECTURE.md:1850-1851`, `:2068`
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only — but the existence of a scheduler is decidable from file state, so this is decisive for the doc-rot question.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — MEDIUM: `ARCHITECTURE.md:1850-1851` and `:2068` are falsified by config, settling the Phase 1/2 scheduler contradiction at configuration level in favour of `ARCHITECTURE.md:28-30`)

#### ARCH-07
- **Claim ID**: ARCH-07
- **Domain**: operational
- **Intended state**: `youtube-sync` has a real weekly schedule but ships DISABLED because `youtube_provider` defaults to `fake`; `webcontent-sync` stays manual.
- **Repository-observed state**: Confirmed on all three points. Schedule `cron(0 19 ? * SUN *)` with description "Weekly Khan Academy video catalog refresh (disabled - no real API key)" (`modules/scheduled-jobs/main.tf:108-110`); `enabled = var.youtube_sync_enabled` (`:125`) whose default is `false` in both the module (`variables.tf:63-67`) and the environment (`environments/staging/variables.tf:169-173`, "Blocked on a real `YOUTUBE_API_KEY` (OPEN_DECISIONS #6), so the default is off"); with that default `state` evaluates to `"DISABLED"` (`:198`). `webcontent-sync` is absent by design: "not here at all: it rewrites tracked files under `knowledge-content/` ... it would fail against D-088's `readonlyRootFilesystem = true` regardless" (`:21-24`).
- **Evidence**: as cited above; rationale at `modules/scheduled-jobs/main.tf:112-118`
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; the live schedule's `State` field is Phase 3B. The DISABLED conclusion assumes the unread `terraform.tfvars` does not set `youtube_sync_enabled = true`.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally)

#### ARCH-08
- **Claim ID**: ARCH-08
- **Domain**: deployment
- **Intended state**: Fargate services, RDS Postgres 16, an RDS MySQL fixture, Terraform IaC, env separation at VPC/prefix level.
- **Repository-observed state**: Confirmed at config level. Two Fargate services (`environments/staging/main.tf:391` learning-api, `:517` chat-api) via `modules/ecs-service` with `requires_compatibilities = ["FARGATE"]` (`modules/ecs-service/main.tf:66`), `launch_type = "FARGATE"` (`:313`), ARM64 (`:78`), on `aws_ecs_cluster.this` (`:217`). `module.rds_postgres` (`:248`) → `engine = "postgres"`, `engine_version` default `"16.4"`. `module.rds_mysql` (`:257`) → `engine = "mysql"`, version default `"8.4.10"`, documented as the fixture ("imitates go.intellichoice.org's shape for staging (D-082/D-083/D-084) - it is not the real external system, just IntelliChoice's own seeded fixture DB", `modules/rds-mysql/variables.tf:25-27`). Env separation is by `var.name_prefix` plus a single VPC module, not AWS Organizations. pgvector is at the migration layer (`packages/db/alembic/versions/4001aafe1ebe_*.py` imports `pgvector.sqlalchemy`; `0e846670f363_s13_rag_search_indexes.py` creates an HNSW `vector_cosine_ops` index), not in the terraform parameter group.
- **Evidence**: as cited above; `environments/staging/rds-mysql-schema.sql` present
- **Evidence type**: terraform config + migration source
- **Verification limitations**: Configuration only; that these resources are deployed and running is Phase 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally)

#### ARCH-09
- **Claim ID**: ARCH-09
- **Domain**: deployment
- **Intended state**: Zero Mongo/Atlas resources in terraform (the "managed Mongo (Atlas)" clause is stale).
- **Repository-observed state**: Confirmed. Case-insensitive grep for `mongo|atlas|documentdb` across all `*.tf` and `*.sql` under `terraform/` (excluding `.terraform/`) returns **zero hits**. No `mongodbatlas` provider in `environments/staging/versions.tf`; the lock file carries only `hashicorp/aws` 5.100.0 and `hashicorp/random` 3.9.0. The only NoSQL-adjacent storage is the two RDS instances.
- **Evidence**: the grep result; `terraform/environments/staging/.terraform.lock.hcl`
- **Evidence type**: negative grep (terraform config)
- **Verification limitations**: Configuration only; no live account inventory.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally)

#### ARCH-10
- **Claim ID**: ARCH-10
- **Domain**: architecture
- **Intended state**: learning-api runs 2 ECS tasks.
- **Repository-observed state**: Confirmed for the task-count half. `environments/staging/main.tf:446-447`: `desired_count = 2` and `autoscaling_min_capacity = 2`, with the surrounding comment noting that `desired_count` is in `ignore_changes` so "it is `autoscaling_min_capacity` that actually moves a live service off 1 - the desired_count below only matters to a from-scratch apply" (`:443-445`). Module defaults are `desired_count = 1` / `min = 1`, so 2 is an explicit environment override. `ignore_changes = [task_definition, desired_count]` at `modules/ecs-service/main.tf:370`. The observability module independently encodes the floor: `capacity_floors.learning-api.min_capacity = 2` (`:826-829`).
- **Evidence**: as cited above; `modules/ecs-service/variables.tf:65-69, 187-191`
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; live `desiredCount`/`runningCount` is Phase 3B. The LISTEN/NOTIFY relay code half and the 8000-byte NOTIFY cap were out of this inspector's scope.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally)

#### ARCH-11
- **Claim ID**: ARCH-11
- **Domain**: architecture
- **Intended state**: chat-api scales out on ALB p95 latency.
- **Repository-observed state**: Confirmed, with the policy quoted. `environments/staging/main.tf:544-545`: `enable_latency_step_scaling = true` + `alb_arn_suffix = module.alb.alb_arn_suffix`, rationale at `:539-543` ("chat-api waits on Bedrock, so CPU target-tracking can never fire on its saturation (p95 31s at 15% CPU, measured live) - scale on ALB p95 latency instead"). Mechanism: scale-out `aws_appautoscaling_policy.latency_scale_out`, `policy_type = "StepScaling"` (`modules/ecs-service/main.tf:435`), steps +1 for [0,7) and +2 beyond 7 (`:448-456`); driving alarm `TargetResponseTime` / `AWS/ApplicationELB` / `extended_statistic = "p95"` / `period = 60` / `evaluation_periods = 2` / `threshold = 3` / `treat_missing_data = "notBreaching"` (`:463-475`); scale-in −1 with `evaluation_periods = 15`, `threshold = 1`, driven by a metric-math alarm `expression = "FILL(m1, 0)"` (`:500-565`). Because `aws_appautoscaling_policy.cpu` has `count = var.enable_autoscaling && !var.enable_latency_step_scaling` (`:408`), chat-api has **no** CPU policy — latency replaces rather than augments it. chat-api capacity: no override → module defaults min 1 / max 3; the former `autoscaling_max_capacity = 1` stopgap is gone with the reversal documented at `:547-552` ("D-344 authored `autoscaling_max_capacity = 1` here as a stopgap ... **it was never applied**").
- **Evidence**: as cited above
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; live policy/alarm state is Phase 3B. The relay code and the channel name `chat_session_events` were out of scope.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — config half confirmed: ALB p95 step scaling is exactly what is wired)

#### ARCH-12
- **Claim ID**: ARCH-12
- **Domain**: infrastructure
- **Intended state**: One uvicorn worker per task, so the lever is task count.
- **Repository-observed state**: Confirmed. Neither service container definition sets a `command`/`entryPoint` (`modules/ecs-service/main.tf:82-106`), so the image CMD runs: `apps/learning-api/Dockerfile:125` `CMD ["uvicorn", "learning_api.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips=*", "--timeout-keep-alive", "125"]` and `apps/chat-api/Dockerfile:83` the chat equivalent on 8002 — **no `--workers`**, i.e. one worker. Terraform records the ceiling: "the container runs ONE uvicorn worker (no --workers), so a single task cannot use more than 1024 CPU units no matter what is provisioned - past that the lever is task count, not task size" (`environments/staging/main.tf:428-431`). Sizing: learning-api `cpu = 512`, `memory = 1024` (`:432-433`) plus `pin_app_container_cpu = true` (`:438`) setting the app container's `cpu` to 512 − 128 = 384, leaving 128 to the sidecar; chat-api sets no cpu/memory → module defaults 256 / 512.
- **Evidence**: as cited above; `modules/ecs-service/main.tf:85-88`; `modules/ecs-service/variables.tf:53-63, 250-259`; `modules/ops-task/main.tf:33-35`
- **Evidence type**: terraform config + Dockerfiles
- **Verification limitations**: Configuration only; the measured throughput/latency numbers (5 concurrent/task, concurrency^1.55) are runtime measurements — Phase 3B. Note chat-api runs at 256/512 while learning-api runs at 512/1024, so ARCH-12/13's per-task capacity figures are not uniform across services.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — the one-worker-per-task and CPU-sizing halves are confirmed in configuration)

#### ARCH-13
- **Claim ID**: ARCH-13
- **Domain**: infrastructure
- **Intended state**: The capacity/pricing table's "today" row is 2 tasks.
- **Repository-observed state**: Confirmed for learning-api. `desired_count = 2` / `autoscaling_min_capacity = 2` (`environments/staging/main.tf:446-447`), max at module default 3 (`modules/ecs-service/variables.tf:193-197`, "Deliberately modest (Free Tier + solo-maintainer scale, not enterprise headroom)"). chat-api is min 1 / max 3. So the pinned-2 configuration exists, but the ceiling is 3 tasks per service — a capacity plan needing five tasks at 25 concurrent would exceed the configured `max_capacity`.
- **Evidence**: as cited above
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; the measured p95 points and the interpolation are runtime facts — Phase 3B. The extrapolation ban is a doc-internal rule, not checkable here.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — drift adjudicated DOWN to LOW-MEDIUM from the inspector's MEDIUM: the r=5 plan would need 5 tasks vs configured max 3, but D-153 §3 WITHDREW that purchase, so no active plan exceeds config. Record as a latency-plan-vs-ceiling note for whenever capacity is revisited, not a live mismatch.)

#### ARCH-14
- **Claim ID**: ARCH-14
- **Domain**: infrastructure
- **Intended state**: The RDS instance class is `db.t4g.micro`.
- **Repository-observed state**: Confirmed for both engines, by default with no environment override. `modules/rds-postgres/variables.tf:23-33` → `default = "db.t4g.micro"`, description: "db.t4g.micro (Free Tier eligible) - this AWS account has Free Tier restrictions active (confirmed via a real CreateDBInstance rejection during S32/D-084), so a non-eligible class like db.t4g.small is rejected outright, not just costed differently." `modules/rds-mysql/variables.tf:23-31` same default. `environments/staging/main.tf:248-264` passes no `instance_class`. `multi_az` default `false` on both (`rds-postgres/variables.tf:46-50`).
- **Evidence**: as cited above
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; the live instance class is Phase 3B. The `pool_size=10, max_overflow=10` code half was out of this inspector's scope.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — the config assertion is confirmed in the repository; the deployed-instance assertion is the 3B half)

#### ARCH-15
- **Claim ID**: ARCH-15
- **Domain**: infrastructure
- **Intended state**: Account Free-Tier restrictions rejected `db.t4g.small` with a real `CreateDBInstance` failure.
- **Repository-observed state**: The *account state* is not verifiable from the repository. A code comment **does record the event**: `modules/rds-postgres/variables.tf:25-28` — "this AWS account has Free Tier restrictions active (confirmed via a real CreateDBInstance rejection during S32/D-084), so a non-eligible class like db.t4g.small is rejected outright, not just costed differently." This corroborates the claim's provenance but is a self-report inside the repo, not independent evidence, and says nothing about the account's status today.
- **Evidence**: `terraform/modules/rds-postgres/variables.tf:25-28`
- **Evidence type**: terraform config (comment)
- **Verification limitations**: Current account Free-Tier status and the historical API failure are both out-of-repo. No AWS command was run.
- **Classification**: UNVERIFIED (adjudicated centrally — deferred to Phase 3B, with the corroborating in-repo comment noted)

#### ARCH-16
- **Claim ID**: ARCH-16
- **Domain**: architecture
- **Intended state**: Neither `/stream` route may hold a pooled DB connection for the life of the SSE response; the initial snapshot is built in a short-lived session.
- **Repository-observed state**: Confirmed on both routes. Each acquires a session directly from `request.app.state.db_session_factory` inside an `async with` that closes **before** the generator is created; the keep-alive loop (`asyncio.wait_for(queue.get(), timeout=KEEPALIVE_INTERVAL_S)`) touches no DB object. learning-api uses `session_scope(...)` (commits on clean exit) because its initial snapshot writes a `stage_transitions` row; chat-api uses the bare factory because its snapshot is read-only. Neither handler declares `Depends(get_db_session)`.
- **Evidence**: `apps/learning-api/src/learning_api/routers/stream.py:330-333` with comment at `:313-315` ("The keep-alive loop below needs no database at all."); `apps/chat-api/src/chat_api/routers/stream.py:143-145` with comment at `:136-141` ("**20 concurrent SSE connections exhausted it**"); loop bodies at learning `stream.py:337-347`, chat `stream.py:147-157`
- **Evidence type**: code
- **Verification limitations**: The "20 concurrent streams exhausted 10+10" measurement is a documented claim not reproducible read-only; pool size was not verified against deployed config. Static reading cannot exclude a pooled connection held indirectly by `graph.aget_state` (the LangGraph saver has its own psycopg pool, outside this invariant).
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally)

#### ARCH-17
- **Claim ID**: ARCH-17
- **Domain**: operational
- **Intended state**: (observed-state claim) The two-store commit seam is real; `checkpoint_reconcile.py` rolls the checkpoint backwards only; `learning_checkpoint_repairs_total` counts it; the fix covers seam (a) mid-finalize only — seam (b) mid-interrupt and the commit ordering remain open.
- **Repository-observed state**: Fully corroborated by code, including the two open remainders stated in-code. `checkpoint_reconcile.find_repair` returns only backwards repairs (`{"study_session_id": None, "phase": "pre_exam"}`) and returns `None` for seam (b) with an explicit comment that no detection shipped. No later fix exists: the only repair call site is `_reconcile_checkpoint`, and the saver still does not share the request connection.
- **Evidence**: `apps/learning-api/src/learning_api/services/checkpoint_reconcile.py:4-9` ("the domain rows commit at FastAPI **dependency teardown**... A task stop enters that window with no bug required, and ECS drains tasks on every deploy."), `:22-25` ("It does not fix the ordering... stays open"; "always rolls *backwards* to a state the database already supports"), `:88-99` ("(b) mid-interrupt is NOT handled here... So seam (b) stays open and AUD-X-07 stays open with it."); `apps/learning-api/src/learning_api/routers/sessions.py:735-757`; `packages/observability/src/intellichoice_observability/metrics.py:51-54`
- **Evidence type**: code (including self-attesting comments) + metric declaration and single increment site
- **Verification limitations**: "ECS drains tasks on every deploy" is an AWS-behaviour claim not verifiable from this repo; the reproduction test was not run. The absence of a later fix is an absence-of-evidence result from targeted greps, not exhaustive.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — both open seams confirmed still open, matching the claim)

#### ARCH-18
- **Claim ID**: ARCH-18
- **Domain**: architecture
- **Intended state**: Every learning route passes a required `access: "read" | "write"`; tutor/branch_manager reads unscoped, writes fail closed; resolution awaits S43's `IcProfileAdapter`.
- **Repository-observed state**: Confirmed on all three sub-claims. `Access` is a required keyword-only parameter (no default), every call site supplies it, writes 403, reads pass through.
- **Evidence**: `apps/learning-api/src/learning_api/authorization.py:7-14` — `Access = Literal["read", "write"]` with "Required at every call site rather than defaulted, because the recurring defect in this codebase is a route that quietly gets the permissive branch: AUD-C-01, AUD-X-01 and AUD-X-05 ... A new route cannot compile without answering the question."; `:22` `access: Access` after `*`; `:66-71` write refusal / read fall-through; `:52` "S43's `IcProfileAdapter` is what unblocks it"
- **Evidence type**: code + call-site enumeration
- **Verification limitations**: "Every learning route" was verified as "every `resolve_target_student` call site"; a route that never calls it would not be caught by this inspection.
- **Classification**: CONFIRMED_IN_REPOSITORY (the shared expiry-vs-frozen-closure drift is carried once under REQ-09/SEC-09/ARCH-18)

#### ARCH-19
- **Claim ID**: ARCH-19
- **Domain**: architecture
- **Intended state**: ARCHITECTURE.md's storage-split table is the canonical as-built layout: Postgres holds curriculum, assessments, checkpoints, MCP audit trail, RAG+pgvector, YouTube catalog, org directory, cost reservations, rate-limit counters, chat/memory/report tables; MySQL holds PII read-only via `MySQLProfileAdapter`.
- **Repository-observed state**: Every Postgres-side row in the table is present as real models/migrations — curriculum, assessments (5 tables), checkpoints (4, created by LangGraph's `AsyncPostgresSaver`, deliberately outside `Base.metadata` and excluded from autogenerate), `mcp_tool_calls`, RAG + pgvector (`rag_chunks` with `Vector(EMBEDDING_DIM)`), `youtube_videos`, org directory (3), `cost_reservations`, `rate_limit_events`, chat/memory/report (6), `learning_sessions`, `chat_turn_cancellations`, `chat_escalation_sends`. **Absent from the table but present in Postgres** (the table under-describes reality): `study_sessions`, `study_items`, `study_attempts`, `mastery`, `learning_gain`, `hint_events`, `stage_transitions`, `interrupt_approvals`, `question_templates`, `question_variants`, `question_validation_runs`, `evaluation_results` — 37 tables total. MySQL side is a locally-provisioned fixture with four tables (`users`, `parent_child_links`, `attendance`, `branches`) read read-only via raw `SELECT`. `knowledge-content/` exists at repo root.
- **Evidence**: 37 `__tablename__` declarations across `packages/db/src/intellichoice_db/models/`; `models/rag.py:3,63`; `packages/db/tests/test_autogenerate_never_drops_the_checkpoint_tables.py:21-26`; `packages/db/src/intellichoice_db/migration_filters.py:21-24`; `packages/adapters/src/intellichoice_adapters/mysql_profile_adapter.py:42-46`; 38 migrations under `packages/db/alembic/versions/`
- **Evidence type**: code + migration source
- **Verification limitations**: Model/migration presence does not prove the deployed Postgres is at head or that engine versions are 16/8.4. "Read-only" is a docstring plus the absence of INSERT/UPDATE in the adapter, not an enforced grant.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — LOW drift: the storage-split table under-describes reality by 12 shipped tables)

#### ARCH-20
- **Claim ID**: ARCH-20
- **Domain**: architecture
- **Intended state**: No real `go.intellichoice.org` connectivity or credential exists.
- **Repository-observed state**: Confirmed. `go.intellichoice.org` appears in terraform **only in comments** — three hits, all prose (`environments/staging/variables.tf:62`, `environments/staging/main.tf:312`, `modules/rds-mysql/variables.tf:25`). Zero hostnames, security-group rules, VPC peering, `aws_vpc_endpoint_service`, Direct Connect/VPN, or external-credential secrets pointing at it. The only MySQL reachable from the tasks is the locally-provisioned `module.rds_mysql` fixture, whose credentials are RDS-managed (`manage_master_user_password = true`, `modules/rds-mysql/main.tf:51`). All secrets referenced are `${var.name_prefix}/...`-namespaced (jwt, staging-token, youtube-api-key, langsmith-api-key).
- **Evidence**: as cited above; `environments/staging/main.tf:698-705` (ops-task MySQL secrets all resolve to `module.rds_mysql.master_user_secret_arn`)
- **Evidence type**: terraform config + negative grep
- **Verification limitations**: Configuration only; whether any out-of-band credential or network path exists in the account is Phase 3B. This confirms the *absence* half; the "integration shape unconfirmed" half is a plan statement not testable here.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — absence of connectivity/credential)

#### ARCH-21
- **Claim ID**: ARCH-21
- **Domain**: infrastructure
- **Intended state**: No six-logical-DB / schema split adopted; the question is open.
- **Repository-observed state**: Confirmed as not-adopted. Terraform creates a single `db_name` per engine and no schema resources — nothing creates `learning`/`rag`/`memory`/`checkpoint_learning`/`checkpoint_chat`/`evaluation`. At the migration layer, `packages/db/alembic/env.py:36` is `target_metadata = Base.metadata` — one metadata object passed unmodified to both offline and online configure calls (`:59`, `:72`), with **no** `include_schemas`, no `schema_translate_map`, no `version_table_schema`. Grep for `CREATE SCHEMA` / `search_path` / `__table_args__ ... schema` across `packages/db` returns no hits; grep for the literal names `checkpoint_learning`/`checkpoint_chat` → zero hits.
- **Evidence**: as cited above
- **Evidence type**: terraform config + code (alembic env.py)
- **Verification limitations**: Configuration only; the live `\dn` schema list is Phase 3B. Whether a decision entry resolving the question exists is a docs-side matter.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the split is not adopted: single metadata, single `db_name`; this resolves the repo half of the ledger's UNKNOWN. The absence of a decision record remains a docs matter — FINAL_ARCH question 5 still unowned.)

#### ARCH-22
- **Claim ID**: ARCH-22
- **Domain**: infrastructure
- **Intended state**: One Postgres database named `intellichoice`.
- **Repository-observed state**: Confirmed at config level. `modules/rds-postgres/variables.tf:52-55` → `variable "db_name" { default = "intellichoice" }`, consumed at `modules/rds-postgres/main.tf:46`; the environment passes no override (`environments/staging/main.tf:248-255`). That single name is threaded to every consumer: `LEARNING_DB_NAME`, `CHAT_DB_NAME`, `DB_NAME` all read `module.rds_postgres.db_name` (`:489`, `:576`, `:693`). Note the MySQL fixture's `db_name` default is *also* `"intellichoice"` (`modules/rds-mysql/variables.tf:43-46`) — same name, different engine/instance, so the claim is precise but the name is not unique across the footprint.
- **Evidence**: as cited above
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; the live database list is Phase 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — config half confirmed)

#### ARCH-23
- **Claim ID**: ARCH-23
- **Domain**: infrastructure
- **Intended state**: (SPEC §5.33) An AWS Organization with 3 accounts, production EKS across 3 AZs with Karpenter/HPA/PDB/NetworkPolicy/IRSA, Aurora PostgreSQL Multi-AZ writer + reader.
- **Repository-observed state**: **Zero of it.** Grep across terraform `*.tf`/`*.sql` for `eks|kubernetes|aurora|karpenter|aws_organizations`: **zero resource hits**; the only matches are two prose comments explicitly rejecting the model — `modules/ecs-service/variables.tf:109-110` ("the ECS equivalent of SPEC §6.22's Kubernetes-shaped 'pod security' item - this deploys to Fargate, not EKS, per D-004/D-082-084") and `modules/ecs-service/main.tf:384-386` ("SPEC §5.33.4 'HPA signals' ... translated to ECS's real equivalent - Fargate has no HPA"). Instead: one VPC with `az_count` default **2**, one ECS Fargate cluster, `aws_db_instance` (not `aws_rds_cluster`) with `engine = "postgres"` and `multi_az = false`, one account, one environment prefix.
- **Evidence**: as cited above; `modules/vpc/variables.tf:12-16`; `docs/SPEC.md:3116-3187`
- **Evidence type**: negative grep (terraform config)
- **Verification limitations**: Configuration only; account-structure verification is Phase 3B. The SPEC text's own existence was confirmed by another worker (ARCH-25 family).
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — MEDIUM, already ledger-known: SPEC §5.33 prescribes what the repo deliberately does not implement, with no SPEC marker; the built footprint matches D-004)

#### ARCH-24
- **Claim ID**: ARCH-24
- **Domain**: infrastructure
- **Intended state**: (SPEC §5.33.4) HPA on CPU / memory / active-requests / SSE-connections / P95, plus worker scaling on SQS queue depth.
- **Repository-observed state**: Exactly **one** signal is live in config per service, and it is P95 only. Both services set `enable_latency_step_scaling = true` (`environments/staging/main.tf:457`, `:544`), and `aws_appautoscaling_policy.cpu`'s count is `var.enable_autoscaling && !var.enable_latency_step_scaling` (`modules/ecs-service/main.tf:408`) — so the CPU target-tracking policy (`ECSServiceAverageCPUUtilization` @ 70%) is **instantiated for neither service**. Configured signals: `AWS/ApplicationELB TargetResponseTime` p95 step-scaling out (threshold 3s, 2×60s) and in (threshold 1s, 15×60s with `FILL(m1,0)`). Not configured anywhere: memory-based scaling, `ALBRequestCountPerTarget`, SSE-connection-count scaling, and **any SQS resource at all** (grep `sqs` → zero hits in terraform). Bounds: learning-api 2–3, chat-api 1–3. Memory is watched only as an *alarm* (`ecs_memory_alarm_mib = 716`, `:798`).
- **Evidence**: as cited above; `modules/ecs-service/main.tf:384-397, 415-422`; `modules/ecs-service/variables.tf:199-202`
- **Evidence type**: negative grep + terraform config
- **Verification limitations**: Configuration only; live policy inventory is Phase 3B. SPEC's numeric targets are requirements not checkable from terraform and remain 3B.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — MEDIUM: exactly one autoscaling signal configured per service vs SPEC §5.33.4's five-signal HPA + SQS model. Plus LOW-MEDIUM: `modules/observability/main.tf:156`'s comment "one ECS task, one uvicorn worker, no autoscaling" is stale against `desired_count=2` plus two active step-scaling policies.)

#### ARCH-25
- **Claim ID**: ARCH-25
- **Domain**: infrastructure
- **Intended state**: SPEC §5.36's technology-placement table is superseded for the EKS/Kubernetes rows by D-004.
- **Repository-observed state**: Confirmed — **no amendment marker.** The table runs from the `## 5.36 Final Technology Placement` heading to the section end at `docs/SPEC.md:3462`, immediately followed by `---` and `# 6.`; there is no banner, footnote, strikethrough, or D-004 reference anywhere in or around it. `| Kubernetes | EKS runtime |` and `| Enterprise-Level Product | ... CI/CD, EKS |` stand unqualified, as do `| LangFuse | Not used |` and the YouTube weekly-sync row. SPEC's only amendment marker in the whole file is at `:1973` (D-351), for an unrelated section.
- **Evidence**: `docs/SPEC.md:3411-3462`; grep for `superseded|amended|D-004` in SPEC.md returns only `:48` and `:1973`
- **Evidence type**: docs
- **Verification limitations**: None material.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — MEDIUM drift: SPEC §5.36 unmarked against D-004; folds into the SPEC-unmarked-departure family with WORK-31/REQ-35/REQ-37/REQ-43)

#### ARCH-26
- **Claim ID**: ARCH-26
- **Domain**: deployment
- **Intended state**: HISTORICAL — S33/S34 shipped and D-004 was accepted, so FINAL_ARCHITECTURE's status claims are 2026-07-21 projections.
- **Repository-observed state**: Both shipped, with session records. PROGRESS records "**S33 (Security hardening) shipped, 2026-07-23** — see D-085 through D-094" and "**S34 (Load testing and production readiness) shipped, 2026-07-24** — see D-095". D-004 is recorded `accepted, decided at S32 2026-07-22`. So all three of FINAL_ARCHITECTURE's status claims (S32 decision-gated, D-004 "proposed", S33/S34 "not started") are stale, and the file was never regenerated as its own L183-185 instructs.
- **Evidence**: `docs/PROGRESS.md:10456` (S33 shipped); `docs/PROGRESS.md:10364` (S34 shipped); `docs/DECISIONS.md:29` (D-004 accepted 2026-07-22); `docs/PROGRESS.md:10450` (S33 ZAP carry-overs still open); `docs/FINAL_ARCHITECTURE.md:183-185`
- **Evidence type**: docs
- **Verification limitations**: Shipped status read from PROGRESS session records, not from deliverable-by-deliverable verification (WAF-class controls, load tests and canary individually unchecked).
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — **HIGH**: an architecture document a reader would trust for deployment state presents three superseded status claims as current)

#### ARCH-27
- **Claim ID**: ARCH-27
- **Domain**: architecture
- **Intended state**: HISTORICAL — FINAL_ARCHITECTURE's "known gap" (single-instance SSE bus) is closed by D-334/D-335 and D-349 for chat-api.
- **Repository-observed state**: ARCHITECTURE.md's ARCH-10 block confirms the exact remedy FINAL_ARCHITECTURE said nobody had scheduled: `SessionEventBus` fronted by `SessionEventRelay` over Postgres `LISTEN`/`NOTIFY`, measured 2-of-4 → 8-of-8 staging delivery, and "**`chat-api` has the same relay since D-349**".
- **Evidence**: `docs/ARCHITECTURE.md:610-631`; `docs/FINAL_ARCHITECTURE.md:112-120`, `:146-152`, `:175-176`
- **Evidence type**: docs
- **Verification limitations**: Per the §9 evidence line ("none beyond ARCH-10's verification"), no independent verification was owed or performed.
- **Classification**: NOT_APPLICABLE_TO_REPOSITORY (adjudicated centrally — per brief; the underlying staleness is carried by ARCH-26)

#### ARCH-28
- **Claim ID**: ARCH-28
- **Domain**: observability-egress
- **Intended state**: Private subnets carry no `0.0.0.0/0` route; ECR/Logs/Secrets Manager/Bedrock/X-Ray/S3 reach tasks via VPC endpoints; zero NAT gateways.
- **Repository-observed state**: The **PrivateLink half is confirmed**; the **zero-NAT half is conditional and, on current checked-in defaults, false in config.** Endpoints (`modules/vpc/main.tf:142-191`): interface endpoints for `ecr.api`, `ecr.dkr`, `logs`, `secretsmanager` unconditionally, plus `bedrock-runtime` when `var.bedrock_runtime_endpoint_enabled` (default true), plus `xray` when `var.xray_endpoint_enabled` (passed as `var.enable_otel_tracing`) — all six gated on `enable_interface_endpoints` (default true), plus an S3 **Gateway** endpoint on the private route table (`:183-191`). All interface endpoints deliberately in ONE subnet (`subnet_ids = [aws_subnet.private[0].id]`, `:174`) for the per-AZ cost reason at `:168-173`. Route tables: `aws_route_table.public` has an IGW default route (`:45-54`); `aws_route_table.private` (`:96-100`) is declared with **no inline route**, deliberately, so the only default route is the separate counted `aws_route "private_nat"` with `count = var.nat_gateway_enabled ? 1 : 0` (`:105-110`). NAT: `aws_eip.nat` and `aws_nat_gateway.this` both `count = var.nat_gateway_enabled ? 1 : 0` (`:78-94`), one gateway, with "Deliberately **one** NAT, in the first AZ, not one per AZ. It costs ~$33/month per gateway and the traffic crossing it is telemetry" (`:73-77`). **On the checked-in defaults `nat_gateway_enabled` evaluates TRUE**: `environments/staging/main.tf:136` `nat_gateway_enabled = local.needs_private_egress`, and `langsmith_tracing_enabled` defaults `true` (`environments/staging/variables.tf:183-189`, "Turned on 2026-08-06 at the user's explicit request").
- **Evidence**: as cited above
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; the actual NAT count and route table in AWS is Phase 3B. `terraform.tfvars` **exists** and was not read — it could set `langsmith_tracing_enabled = false`, flipping the config to zero NAT. The config-level NAT count is therefore 1-with-defaults, indeterminate-with-tfvars.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — the PrivateLink set and the no-inline-default-route design are CONFIRMED; the zero-NAT property is conditional and OFF under checked-in defaults. Drift LOW-MEDIUM: ARCHITECTURE's zero-egress framing is baseline-with-exception.)

#### ARCH-29
- **Claim ID**: ARCH-29
- **Domain**: observability-egress
- **Intended state**: (ARCHITECTURE.md) One NAT in one AZ, deliberately; both NAT and tracing gated on a *single* `langsmith_tracing_enabled` flag. (D-419: NAT "absent from the plan entirely".)
- **Repository-observed state**: The single-flag description is **superseded by config** — the gate is a **consumer map**, exactly D-406: `private_egress_consumers = { langsmith_tracing = var.langsmith_tracing_enabled, youtube_sync = var.youtube_sync_enabled }` / `needs_private_egress = anytrue(values(local.private_egress_consumers))` (`environments/staging/main.tf:115-119`), consumed at `:136`. The prior wiring and the reason it changed are recorded in place at `:101-114` ("the previous wiring (`nat_gateway_enabled = var.langsmith_tracing_enabled`) was one consumer hardcoded as the condition ... `youtube-sync` also runs in a private subnet with `assign_public_ip = false`, and the YouTube Data API has no VPC endpoint"), with a matching note at `modules/scheduled-jobs/main.tf:120-124`. "One NAT in one AZ deliberately, telemetry not function" is confirmed verbatim (`modules/vpc/main.tf:73-77`). With `youtube_sync_enabled = false` by default, LangSmith is currently the only *active* egress consumer — true today but structurally no longer exclusive. On D-419's "absent from the plan entirely": with checked-in defaults the NAT resources are **present** in configuration (count = 1).
- **Evidence**: as cited above
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; live NAT count/billing and actual plan output are Phase 3B. The tfvars override path is unreadable by instruction, so the config-level NAT count is determinate only under defaults. The D-419 tension is unresolvable in 3A (tfvars unread, plan forbidden).
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally, as a claim about the doc's description — two findings: (1) DOCUMENTATION_DRIFT MEDIUM, `ARCHITECTURE.md:2161-2174`'s "single `langsmith_tracing_enabled` flag" is superseded by D-406's two-consumer map; (2) the D-419 "absent from the plan entirely" tension is explicitly deferred to 3B with the tfvars question flagged. Recorded as hypothesis, not fact: D-419's sentence may describe the plan DIFF rather than NAT absence; 3B should check live NAT count first.)

#### ARCH-30
- **Claim ID**: ARCH-30
- **Domain**: observability-egress
- **Intended state**: Four observability sinks; exactly 4 Bedrock metric filters per service; a per-task `otel-collector` sidecar; LangSmith inputs/outputs forced masked.
- **Repository-observed state**: All four elements present in config. The 4 Bedrock filters are declared `for_each = var.log_group_names` with metric names `BedrockCostCents`, `BedrockCallDurationMs`, `BedrockCallFailed`, `BedrockCircuitOpen` (`dashboard.tf:49/67/84/130`). The sidecar is a non-essential container named `otel-collector` in the shared ecs-service task definition (`enable_otel_sidecar`), exporting OTLP→`awsxray`. Masking is **not** in terraform — it is forced in Python: `configure_langsmith()` sets `LANGSMITH_HIDE_INPUTS`/`_OUTPUTS = "true"` unconditionally (not `setdefault`, unlike `LANGSMITH_PROJECT`), with a test asserting it.
- **Evidence**: `terraform/modules/observability/dashboard.tf:49-143`; `terraform/modules/ecs-service/main.tf:108-160`; `packages/observability/src/intellichoice_observability/langsmith_config.py:36-42`; `packages/observability/tests/test_langsmith_config.py:8-41`
- **Evidence type**: terraform config + code + test-source
- **Verification limitations**: "Never leaves AWS" is a runtime egress property (VPC-endpoint routing confirmed under ARCH-28; live traffic → 3B). Whether the sidecar is actually running per task is 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — LOW drift: the ledger locates masking in "task definitions"; it is enforced in application code, so a task definition alone would not show it)

#### ARCH-31
- **Claim ID**: ARCH-31
- **Domain**: observability-egress
- **Intended state**: `LANGSMITH_WORKSPACE_ID` is now set; a new per-service `LangSmithIngestFailed` filter exists because the 4 Bedrock filters watched nothing about delivery.
- **Repository-observed state**: Both confirmed. `LANGSMITH_WORKSPACE_ID = var.langsmith_workspace_id` is in `local.langsmith_env` merged into **both** services' env (`staging/main.tf:160-178`), with the 403/no-default-workspace root cause written at the variable. The filter (`dashboard.tf:112`, pattern `{ $.logger = "langsmith.client" }`) and the alarm (`alarms.tf:56-83`) are both `for_each = var.log_group_names` → one per service. `alarms.tf:8-11` independently records the history ("four Bedrock metric filters per service ... none of them watched telemetry delivery").
- **Evidence**: `terraform/environments/staging/main.tf:154-178`; `terraform/environments/staging/variables.tf:175-181`; `terraform/modules/observability/dashboard.tf:112-127`; `terraform/modules/observability/alarms.tf:56-83`; in-repo commit `a53a5ed` "terraform: declare LANGSMITH_WORKSPACE_ID, which was applied but never committed"
- **Evidence type**: terraform config + git history
- **Verification limitations**: The outage itself and the 2026-08-10 go-live are historical/live facts; only the config artefacts of the fix are verifiable here.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the fix's config artefacts all exist; the outage narrative is historical-corroborated. No drift.)

#### ARCH-32
- **Claim ID**: ARCH-32
- **Domain**: observability-egress
- **Intended state**: Health endpoints emit no telemetry at all, suppressed at the `/readyz` handler, so the scanned trace corpus is real traffic rather than ~97% ALB health checks.
- **Repository-observed state**: Two-layer suppression, both present. (a) `instrument_fastapi_app` passes `excluded_urls=HEALTH_ENDPOINT_URLS` = `"healthz,readyz"`, with `/metrics` deliberately not excluded. (b) Both apps wrap the **whole** `/readyz` body in `suppress_instrumentation()` — the handler-level suppression the claim names — and chat-api's comment states the reasoning ("the whole handler emits no telemetry, not each query individually. Suppressing per-query is what failed here"). Six tests exist in `test_health_endpoint_tracing.py`, including negative arms.
- **Evidence**: `packages/observability/src/intellichoice_observability/tracing.py:169-191`; `apps/chat-api/src/chat_api/main.py:342-348`; `apps/learning-api/src/learning_api/main.py:432-435` "AUD-F-30: suppressed at the handler, not per query"; `packages/observability/tests/test_health_endpoint_tracing.py:51,87,261`
- **Evidence type**: code + test-source
- **Verification limitations**: Tests unexecuted; the "3.4× worse" first attempt and the ~97% measurement are historical claims not re-derivable from the repo. Scope word: **traces** are suppressed, but the access-log middleware (`install_request_logging_middleware`) has no path exclusion, so `/readyz` still produces one JSON log line per poll.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — LOW drift: "no telemetry at all" is true of traces only; `/readyz` still emits an access-log line per poll)

#### ARCH-33
- **Claim ID**: ARCH-33
- **Domain**: deployment
- **Intended state**: The deploy gate asserts exactly one `PRIMARY` deployment, image tag == this run's, `runningCount ≥ 1`, and `rolloutState == COMPLETED` bound-retried; a deterministic Vite content-hash comparison covers the S3/CloudFront half.
- **Repository-observed state**: **The ECS half is confirmed exactly; the Vite-hash half is not in the pipeline.** The gate step "Verify the running image is this commit (deployed-version gate)" asserts `len(d) != 1 → FATAL`, `status != 'PRIMARY' → FATAL`, `rolloutState == 'FAILED' → FATAL`, `desiredCount < 1 → FATAL`, `runningCount < 1 → FATAL`, then compares `TAG != EXPECTED → exit 1` *outside* the retry ("Checked on every pass, including PENDING"), with the retry bounded by `WAIT_SECONDS=300` / `sleep 15` and an `::warning` on timeout acceptance. `runningCount == desiredCount` is indeed the dropped assertion. But grepping the whole 711-line workflow for `sha256|md5|ETag|content-hash|dist/|vite` yields **no hash-comparison step**; frontend verification is `aws s3 sync ... --delete` plus a CloudFront invalidation plus three curls (`/`, `/`, `/me` must be 401). `ARCHITECTURE.md:456-458` itself phrases the hash check as "building the commit locally and comparing" — a manual procedure — and no `make` target or script implements it either.
- **Evidence**: `.github/workflows/deploy-staging.yml:409-501`, `:667-711`; `docs/ARCHITECTURE.md:455-458`
- **Evidence type**: CI config + negative grep
- **Verification limitations**: Whether the gate has ever fired or behaved as designed is 3B.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — MEDIUM drift: the ECS control-plane gate is exactly as documented, but the Vite content-hash comparison ARCHITECTURE.md presents as the "second, independent answer" is a manual technique with no workflow step, script, or make target; the S3/CloudFront half of every deploy is covered only by three curls)

#### ARCH-34
- **Claim ID**: ARCH-34
- **Domain**: deployment
- **Intended state**: `scripts/check_deployed_image_consistency.py` / `make image-check` exists, judges each service against its family's latest revision, reports the tfvars pin without failing on it; `adopt_deployed_image` defaults true.
- **Repository-observed state**: All three confirmed. `image-check` is in `.PHONY` and defined at `Makefile:292-294` invoking `scripts/check_deployed_image_consistency.py`; the target's comment records the D-417/A3 rename from `tfvars-floor-check` and the measurement ("with the pin two deploys stale, `terraform plan` moved the image **forward** to what was running"). `variable "adopt_deployed_image"` has `default = true` and is consumed by the `for_each` guard at `staging/main.tf:12`. The ARCHITECTURE.md coverage gap reproduces: lines 429-458 stop at the ECS control-plane and frontend-hash checks with no mention of `image-check`.
- **Evidence**: `Makefile:1,280-294`; `scripts/check_deployed_image_consistency.py`; `terraform/environments/staging/variables.tf:201-214`; `terraform/environments/staging/main.tf:7-42`
- **Evidence type**: code + CI/build config + terraform config + negative doc grep
- **Verification limitations**: The script requires live AWS (`aws configure export-credentials`), so its *judgement* is 3B. It is not wired into CI or `deploy-staging.yml` — operator-invoked only.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — LOW drift: `make image-check` is operator-invoked only, wired into neither CI nor `deploy-staging.yml`, which the claim does not state)

#### ARCH-35
- **Claim ID**: ARCH-35
- **Domain**: operational
- **Intended state**: The org time convention is a provisional default with an env switch (`ORG_TIMEZONE`/`ORG_TIME_CONVENTION`).
- **Repository-observed state**: Confirmed, and there are **three** variables, not two. Both task definitions carry `ORG_TIMEZONE = var.org_timezone`, `ORG_TIME_CONVENTION = var.org_time_convention`, `ORG_TIME_CONFIRMED = var.org_time_confirmed ? "true" : "false"` (learning-api at `main.tf:497-499`, chat-api at `:582-584`) — `ORG_TIME_CONFIRMED` is exactly the "provisional" marker the claim describes in prose.
- **Evidence**: `terraform/environments/staging/main.tf:497-499,582-584`
- **Evidence type**: terraform config
- **Verification limitations**: The grade-on-submit half and the S43-owed property guard were out of this inspector's area (frozen with S43) and were not inspected.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — no drift)

### 3.3 SEC family — 27 claims

#### SEC-01
- **Claim ID**: SEC-01
- **Domain**: data-boundary
- **Intended state**: MySQL is the sole store for names, emails, roles, relationships, grade, branch, manager email, attendance, account status; Postgres may store only shared external identifiers and must never replicate names, emails, phones, addresses.
- **Repository-observed state**: `MySQLProfileAdapter` is the only reader of PII, all raw `SELECT`s, no INSERT/UPDATE anywhere in it; names/emails/grade/attendance come from `users`, `branches`, `attendance`, `parent_child_links`. Postgres models carry 35 `*_external_id` columns. Four PII-shaped Postgres columns exist and are exempted by decision: `org_branches.address/phone/email` and `org_team_members.name`. `BranchInfo.manager_email` is returned by the adapter from MySQL `branches.manager_email` and is not persisted to Postgres (`org_branches.email` is the scraped public branch address, sourced from `packages/webcontent`, with `source_url`/`content_hash` columns confirming provenance).
- **Evidence**: `packages/adapters/src/intellichoice_adapters/mysql_profile_adapter.py:44-46`, `:56-59`, `:104-117`, `:119-145`; `packages/db/src/intellichoice_db/models/org.py:18-33`; `packages/db/tests/test_schema_purity.py:6-11,48-53`
- **Evidence type**: code + test-source
- **Verification limitations**: Does not prove the MySQL grant is actually read-only at the database level, nor that no runtime path writes MySQL PII into a Postgres free-text column — only column *names* are checked.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally, from the inspector's PARTIALLY_IMPLEMENTED — the four exempt columns are org-published public content under D-050. One LOW-MEDIUM doc-drift entry covers REQ-01 and SEC-01 together: SPEC and INCIDENT_RESPONSE state the rule absolutely without the exemption.)

#### SEC-02
- **Claim ID**: SEC-02
- **Domain**: data-boundary
- **Intended state**: MySQL and Postgres results must be combined in the FastAPI service layer joined by external primary key, never a federated SQL join; no warehouse copy of MySQL PII into operational Postgres.
- **Repository-observed state**: No federated-join machinery exists: grep for `dblink|postgres_fdw|mysql_fdw|FOREIGN DATA WRAPPER|warehouse` across `packages/`, `apps/`, `terraform/` (`.py/.tf/.sql`) returns one unrelated IAM `type = "Federated"` line and nothing else. The two databases are two separate engines (`app.state.db_engine`, `app.state.profile_adapter.engine`). Service-layer joins by external id are visible in Python: `routers/parents.py` loops `get_parent_children` → `get_student_profile` → `get_branch`; `services/attendance.py:141-143` does the same. All 21 app-level adapter call sites go through `profile_adapter.<method>`.
- **Evidence**: `apps/learning-api/src/learning_api/routers/parents.py:50-67`; `apps/learning-api/src/learning_api/services/attendance.py:102,141-143`; `apps/learning-api/src/learning_api/main.py:101` and `apps/chat-api/src/chat_api/main.py:78` (two independent engines); negative grep for FDW/dblink/warehouse
- **Evidence type**: code + negative grep
- **Verification limitations**: Absence proven by grep over the named extensions only; a federated join created by hand in a live database, or in an unscanned file type, would not appear. Does not prove no analytics export exists outside the repo.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### SEC-03
- **Claim ID**: SEC-03
- **Domain**: privacy
- **Intended state**: Bedrock payloads may carry only `grade`, `current_topic`, `skill`, `estimated_level`, `question`, `selected_answer`, `relevant_learning_fact`; `full_name`, `email`, `phone`, `home_address`, `precise_location`, `parent_contact`, `branch_manager_email` must never be sent.
- **Repository-observed state**: **Denylist half fully honoured** — none of SPEC's seven forbidden names appears in any of the 23 `*Payload` models, and the test denylist is a superset (adding `display_name`, `name`, `address`, `location`, `student_external_id`, `parent_external_id`, `raw_message`, `message`). **Allowlist half: only one model matches SPEC's list.** `BedrockTutorPayload` is SPEC's seven fields verbatim (`bedrock.py:91-109`). The other 16 governed models carry fields not in SPEC's list, e.g. `HintPersonalizationPayload` (+`canonical_hint_text`, `misconception_tag`, `attempt_count`, `hint_level`, `previous_hint_summaries`; −`current_topic`, `estimated_level`), `StageNarrativePayload` (14 fields including **`attendance_status`**), `ReportInterpretationPayload` (19 fields), `RagAnswerPayload` (`query`, **`user_role`**, `context_chunks` — a role string, where D-219 removed `user_role` from `ScopeAndIntentPayload` for prompt-authorization reasons while leaving it here), `TutorChatPayload` (+`redacted_message`), plus rerank/calendar/video/memory payloads. No SPEC-listed field is missing from the union — SPEC's list is a strict subset of what code sends. Six further payloads are under `extra="forbid"` only with no field allowlist; `LlmJudgePayload` is explicitly ungoverned with a written reason.
- **Evidence**: `docs/SPEC.md:2812-2836`; `packages/shared/src/intellichoice_shared/bedrock.py:91-109`, `:157-170`, `:796-807` "`query`/`user_role`/`context_chunks`", `:1120-1137` "`attendance_status: str | None`"; `packages/shared/tests/test_bedrock_payload_pii_floor.py:60-240`
- **Evidence type**: code + test-source + docs
- **Verification limitations**: Field-name diff only. The test file flags a live gap this diff cannot close: "that the query text itself is not redacted before the wire is a separate, live finding (AUD-C-24)" (`:174-175`), so free-text fields may carry PII the field names cannot reveal. No test executed.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally, down from the inspector's IMPLEMENTATION_DRIFT — MEDIUM: the payload-surface widenings were each decided (D-023/D-071/D-072 wire-allowlist extensions; D-219 removed `user_role` from `ScopeAndIntent` only) but SPEC §5.30.1 still describes exactly one of 23 payloads. The denylist half fully holds; free-text residue AUD-C-24 is a live limitation, not new drift.)

#### SEC-04
- **Claim ID**: SEC-04
- **Domain**: authorization
- **Intended state**: All six authorization-matrix rows enforced in the backend/query layer, never in prompts.
- **Repository-observed state**: **anonymous** — enforced (`role_access.resolve_role_context` returns `("public", None)` for `claims is None` at `role_access.py:119-120`; `role_access_filter` yields `audiences=["public","public"]`, `restrict_to_branch=True`, `as_of=now` → SQL predicates in `rag.py:_apply_filters`; session ownership guarded by `_assert_session_access` and `resolve_role`'s owner-preserving write at `nodes.py:305-306`). **student** — enforced twice (chat-api audience filter plus branch from the student's own profile at `role_access.py:121-123`; learning-api `authorization.py:30-36` and `routers/questions.py:47-50`). **parent** — enforced (`authorization.py:38-45` live MySQL link lookup; `routers/parents.py:44-48` gates the children route to `Role.PARENT`). **tutor** — **not** enforced per-student (`authorization.py:47-71` documents the fall-through as D-086's accepted risk; writes now fail closed, reads keep the gap; in chat-api a tutor gets `audiences=["public","tutor"]` — query-layer enforced — but `branch_external_id` is `None`). **branch_manager** — same as tutor. **admin** — **no backend enforcement exists because no admin role exists**: `packages/shared/src/intellichoice_shared/auth.py:13-17` `Role` has only STUDENT/PARENT/TUTOR/BRANCH_MANAGER; no admin route or role check in either API's routers (the only "admin" strings are the admin-escalation *email recipient*, `config.py:102`).
- **Evidence**: as cited inline above
- **Evidence type**: code
- **Verification limitations**: chat-web/learning-web client-side gating not inspected (not authoritative anyway). No tests executed.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — MEDIUM drift: SPEC §5.30.2's six-role matrix has NO admin role in code at all, so the admin row is unenforceable as specified; tutor/branch_manager rows are partially enforced — audience predicate yes, per-student scope no, the known §7-R8)

#### SEC-05
- **Claim ID**: SEC-05
- **Domain**: data-boundary
- **Intended state**: `test_schema_purity.py::test_no_model_has_a_pii_column_name` walks every ORM model against a denied-column-name list.
- **Repository-observed state**: The test exists and does walk every model — it iterates `Base.registry.mappers` (registry-wide, not a hand-listed set) and `inspect(mapper.class_).columns` for each. The denylist is non-trivial: 18 names covering names, contact details, DOB, SSN, and (added at AUD-C-27) four IP-address spellings, with an in-file note that nothing would have caught the first raw `client_ip` column before `rate_limit_events` existed. Matching is exact, not substring, with the reason stated (curriculum `Topic.name`/`Skill.name` are lesson names). Four `(table, column)` exemptions.
- **Evidence**: `packages/db/tests/test_schema_purity.py:17-43` (denylist), `:56-66` "for mapper in Base.registry.mappers"
- **Evidence type**: test-source
- **Verification limitations**: Not executed. Coverage depends on every model module being imported so its mapper is registered — `intellichoice_db.models.__init__` was not verified to import all 24 model modules. The exact-match denylist cannot see PII inside free-text or JSON columns, and LangGraph's four checkpoint tables are outside `Base.metadata` and therefore outside this test entirely.
- **Classification**: CONFIRMED_IN_REPOSITORY (test itself unexecuted; LOW note: "over every ORM model" is accurate for mapped models but excludes the four checkpoint tables, which hold the most session state)

#### SEC-06
- **Claim ID**: SEC-06
- **Domain**: privacy
- **Intended state**: Every Bedrock payload is an `extra="forbid"` model with an exact field list, pinned by 12+ tests — three per payload type (exact allowlist match, no denylisted names, extra fields rejected).
- **Repository-observed state**: Exceeded and structurally hardened beyond the doc's description. The three arms exist as parametrized tests over all 17 allowlisted models (51 cases), plus 6 hand-written constructor tests that each pass a real `parent_contact="parent@example.com"` and assert `ValidationError`, plus two completeness tests the doc does not mention: `test_every_bedrock_payload_is_governed_by_one_regime` (discovers `*Payload` classes via `dir(bedrock)` rather than a hand list, and also fails on a *stale* regime entry) and `test_every_nested_model_is_itself_governed` (one-hop recursion). The file documents that "every payload type" was once the claim and "six of twenty was the fact" (AUD-L-05/D-175). Not every payload has an exact field list: 10 are in the `extra="forbid"`-only generation regime, 1 is explicitly ungoverned with a written reason.
- **Evidence**: `packages/shared/tests/test_bedrock_payload_pii_floor.py:10-16`, `:314-337`, `:340-356`, `:359-379`, `:382-455`; `packages/shared/src/intellichoice_shared/bedrock.py:91-109`
- **Evidence type**: test-source + code
- **Verification limitations**: Not executed. `extra="forbid"` stops unknown *keys*; it cannot stop PII placed inside a permitted string field (the file says so of `query`, AUD-C-24).
- **Classification**: CONFIRMED_IN_REPOSITORY (tests unexecuted; LOW note: TRACEABILITY's "every Bedrock payload ... with an exact field list" is still literally wider than code — 11 of 23 payloads have no field allowlist, by a reasoned regime split)

#### SEC-07
- **Claim ID**: SEC-07
- **Domain**: privacy
- **Intended state**: A `RedactingSpanExporter` redacts at the span-export boundary, pinned by `test_sse_token_query_string_is_redacted_before_export`, which drives real instrumentation and carries a negative arm and an explicit vacuity guard.
- **Repository-observed state**: All four elements confirmed at the cited lines. The exporter wraps **both** branches of `build_tracer_provider` — the in-memory test exporter via `SimpleSpanProcessor` and the OTLP exporter via `BatchSpanProcessor` — with the reason stated ("Wrapping only the production branch would make the test path structurally unable to catch a regression"). Three redaction patterns: `?token=`/`access_token`/`api_key` query params, a bare `eyJ...` JWT, and `Bearer <x>`. The test builds a real FastAPI app, calls `instrument_fastapi_app`, issues a real request with a JWT in the query string, and asserts the JWT is gone, `token=REDACTED` present, and the route path survives. Vacuity guard at line 91; negative arm at line 100. Both apps wire the exporter transitively via `configure_tracing_provider` → `build_tracer_provider`.
- **Evidence**: `packages/observability/src/intellichoice_observability/tracing.py:55-61`, `:72-89`, `:119-138`; `packages/observability/tests/test_tracing.py:62-97`, `:91`, `:100-111`
- **Evidence type**: code + test-source
- **Verification limitations**: Not executed. Redaction is at export and covers span **attributes** only — `_redacted` rebuilds the span with cleaned attributes but passes `events=span.events` through untouched, so a credential inside a span event would not be redacted. The shared code path was confirmed, not each app's call-site line.
- **Classification**: CONFIRMED_IN_REPOSITORY (tests unexecuted; LOW note: span EVENTS are not redacted, only attributes)

#### SEC-08
- **Claim ID**: SEC-08
- **Domain**: privacy
- **Intended state**: `scripts/scan_logs_pii.py` (`make scan-logs`) scans live log events with the same patterns/matcher as the trace scanner and fails on truncation, an unreadable window, or zero events; the first authenticated run was CLEAN with a 20/20 control.
- **Repository-observed state**: Script exists and every named failure mode is a distinct non-zero exit. It **imports** `SHAPE_PATTERNS`, `Findings`, `Hit`, `_fixture_patterns`, `_match`, `positive_control` from `scan_xray_pii` rather than re-implementing them. Guards: positive control runs first and returns 2 if any pattern cannot fire ("INVALID - these patterns cannot fire, so a clean result proves nothing"); missing log group → 3; unqueryable slice → 3 ("'I could not look' must not report as CLEAN"); any slice at the 10,000-record Insights cap → 3; zero events → 3. Three staging log groups configured. `LOG_ALLOWLIST` is empty by measurement, with the reasoning left visible. `make scan-logs` exists with `START`/`END`/`MINUTES` passthrough.
- **Evidence**: `scripts/scan_logs_pii.py:45-52` (imported matcher), `:189-193`, `:203-212`, `:216-224`, `:226-235`, `:237-242`; `Makefile:243-250`
- **Evidence type**: code + CI/build config
- **Verification limitations**: Never run (requires live AWS credentials and a real window). The 2026-07-30 CLEAN result and 20/20 control are historical assertions not reproducible from the repo. The script is a manual `make` target — no CI workflow or scheduler invoking it was found, so a single clean run is not continuous assurance.
- **Classification**: CONFIRMED_IN_REPOSITORY (existence and guard structure; results not reproducible. LOW-MEDIUM note: the log scanner is manual-only — nothing runs it on a schedule, a posture known since criterion 9 and kept registered.)

#### SEC-09
- **Claim ID**: SEC-09
- **Domain**: authorization
- **Intended state**: §7-R8 — reads unchecked for tutor and branch_manager; mitigations are the closed write half (S40/D-107) and the secret-gated `/dev/token` (D-097); acceptance expires at first real traffic.
- **Repository-observed state**: The read hole and the write refusal are both present exactly as described, with the AUD-X-05 reasoning inlined. The reach is confirmed: dashboard, history and report routes all call with `access="read"` (`students.py:160,315,366,429`), so a tutor token resolves to any requested student on each.
- **Evidence**: `apps/learning-api/src/learning_api/authorization.py:56-62` — "A read-scope gap discloses data that already exists; the same fall-through on a *write* fabricates data that does not. Measured: a tutor token answered and finalized another student's exam, and those `assessment_attempts` rows are indistinguishable from the student's own"; `:66-71`
- **Evidence type**: code
- **Verification limitations**: The `/dev/token` secret gate was not verified here (see SEC-25), and whether real traffic has begun is not observable from the repository. Code presence of the gap is not measurement of exploitation.
- **Classification**: CONFIRMED_IN_REPOSITORY (the gap is present exactly as accepted; the write half is closed. The expiry-vs-frozen-closure drift is one MEDIUM entry covering three claim IDs: REQ-09, SEC-09, ARCH-18.)

#### SEC-10
- **Claim ID**: SEC-10
- **Domain**: security / accepted risk
- **Intended state**: §7-R9 — the checkpoint→domain commit seam is accepted for the pilot; the evidence of non-occurrence is a flat `learning_checkpoint_repairs_total`, and acceptance is void the moment the counter moves.
- **Repository-observed state**: The metric exists, is incremented at exactly one site, is promoted to CloudWatch (present in both the `filter/kpis` include list and the EMF `metric_declarations` in the ECS collector config) and is rendered on a dashboard widget. **No alarm watches it.** Grepping all of `terraform/` for `checkpoint_repair` returns only the two collector-config entries and the one dashboard series — `terraform/modules/observability/alarms.tf` contains no reference. So the tripwire's only reader is a human opening a "Content health" widget; nothing can page on the counter moving off zero, which is the exact event that voids the acceptance.
- **Evidence**: `packages/observability/src/intellichoice_observability/metrics.py:46-54` ("Should be flat at zero; any movement means requests are dying between the checkpoint commit and the domain commit"); increment at `apps/learning-api/src/learning_api/routers/sessions.py:756`; `terraform/modules/ecs-service/main.tf:209` and `:255`; `terraform/modules/observability/dashboard.tf:436`, `:425-427`; `grep -rn "checkpoint_repair" terraform/` → only those three lines
- **Evidence type**: code + terraform config + negative grep
- **Verification limitations**: Terraform presence does not prove the dashboard or metric filter is deployed, nor that the EMF pipeline emits the series; CloudWatch cannot be read to confirm the counter is in fact flat. "Is the metric read by anyone" is answered only in the negative-alarm sense — a human review cadence outside the repo cannot be excluded.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — NEW MATERIAL DRIFT, MEDIUM-HIGH: the §7-R9 acceptance's expiry condition ("void the moment the counter moves") has no automated detector. 3B cannot resolve this; the gap is in configuration.)

#### SEC-11
- **Claim ID**: SEC-11
- **Domain**: authorization
- **Intended state**: Parents are verified against a live linked-children lookup on every parent-scoped route, 403 otherwise; no token claim is trusted.
- **Repository-observed state**: The live lookup is present and is the only parent path — there is no linked-children token claim read anywhere. Because the check lives inside `resolve_target_student` rather than at each route, it applies to all 17 call sites, not just the dashboard. The one parent-scoped route that takes no student id derives the id from the verified `sub` and does its own live lookup.
- **Evidence**: `apps/learning-api/src/learning_api/authorization.py:38-45` — `if claims.role == Role.PARENT: linked_children = await profile_adapter.get_parent_children(claims.sub); if requested_student_id not in linked_children: raise HTTPException(status_code=403, detail="Parent is not linked to this student")`, docstring `:26-28`; call sites `students.py:160,315,366,429`, `sessions.py` ×10, `stream.py:173,220`, `main.py:464`; `apps/learning-api/src/learning_api/routers/parents.py:34-50` (`GET /me/children`, id from the verified token's `sub`)
- **Evidence type**: code + call-site enumeration
- **Verification limitations**: TRACEABILITY cites `authorization.py:39-43`; the block is now at 38-45 (minor line drift). "Live MySQL" is true of the production adapter by name; the adapter was not read to confirm no caching layer sits behind `get_parent_children`. No test executed.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### SEC-12
- **Claim ID**: SEC-12
- **Domain**: privacy
- **Intended state**: Notice before use; coordinates discarded post-Maps; never persisted to Postgres/MySQL/LangSmith/logs; ZIP/city/address alternative; raw manual address not retained by default.
- **Repository-observed state**: Notice verbatim and shown pre-collection (`nodes.py:218-221`, `:1134`; the modal renders `pending.notice` at `LocationConsentModal.tsx:76`). Coordinates are used only for `maps.geocode` + `maps.compute_routes` and are function-local (`services/branch_locator.py:64-115` and its docstring); nothing writes them to a domain table; the MCP audit row stores no arguments (`repositories/mcp.py:16-26`); no logger call in `branch_locator.py` takes the coordinates. Alternatives: the API accepts `zip_code`/`city`/`address` (`sessions.py:863-869`); the modal exposes ZIP and city only. A manual address is not retained in any domain table; its only persistence is LangGraph's `checkpoint_writes.__resume__` row, deleted by `purge_resume_writes` on the success path.
- **Evidence**: as cited above
- **Evidence type**: code
- **Verification limitations**: LangSmith trace payloads are external and unverifiable here.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — see the REQ-28 LOW drifts, and the SEC-13 coupling: the "not retained by default" clause is satisfied only via the purge, which does not cover every path)

#### SEC-13
- **Claim ID**: SEC-13
- **Domain**: privacy
- **Intended state**: The `__resume__` purge closes the last coordinate leak (AUD-C-03); Phase 3 asks whether it also runs on failure and abandonment.
- **Repository-observed state**: The purge exists exactly as documented (`services/checkpoint_privacy.py:24-30`, a parameterized `DELETE FROM checkpoint_writes WHERE thread_id = :thread_id AND channel = '__resume__'`), but **it has exactly one trigger and it is the successful-resume path only.** In `routers/sessions.py`, the ordering inside `respond_to_interrupt` is `_run_turn(...)` → `if cancelled: ... return cancelled_response` (`:897-905`) → `if isinstance(body, LocationConsentChoice): await purge_resume_writes(db, chat_session_id)` (`:907-914`). Consequences read from the code: (a) a **cancelled** location-consent resume returns before the purge, leaving the coordinates/address in `checkpoint_writes`; (b) any exception inside `_run_turn` (Bedrock/Maps/deadline) skips the purge, and `get_db_session` would not commit a delete that never ran; (c) an **abandoned** consent never writes a `__resume__` row at all, so that path is safe by construction. A declined consent (`approved=False`) does reach the purge. The purge is thread-scoped, not checkpoint-scoped.
- **Evidence**: `apps/chat-api/src/chat_api/services/checkpoint_privacy.py:24-30`; `apps/chat-api/src/chat_api/routers/sessions.py:897-914`; `apps/chat-api/src/chat_api/graph/nodes.py:801`
- **Evidence type**: code
- **Verification limitations**: Whether the saver has already written `__resume__` at the moment of a mid-turn failure was not verified empirically; it is LangGraph-internal behaviour asserted by `checkpoint_privacy.py`'s own docstring ("persists the raw `Command(resume=...)` payload ... for crash-safety while the interrupt is being resumed").
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — **NEW MATERIAL DRIFT, MEDIUM (privacy/minors)**: `purge_resume_writes` is unreachable on the cancelled-resume early return and on any `_run_turn` exception, so precise coordinates or a typed address persist in `checkpoint_writes.__resume__` with no retention job covering that table's rows for live threads. TRACEABILITY's "AUD-C-03 closed the last leak" framing does not hold for those paths — SPEC §5.1.3 exposure class.)

#### SEC-15
- **Claim ID**: SEC-15
- **Domain**: privacy
- **Intended state**: TRACEABILITY records rule 8 as dispositioned rather than traced because the image feature does not exist; `analyze_image` is an unimplemented gateway method deferred to S29.
- **Repository-observed state**: Matches. `analyze_image` is not defined on `BedrockGateway` — it appears only in the module docstring at `packages/shared/src/intellichoice_shared/bedrock.py:5`, which names S29/D-078 explicitly and states the project's "don't stub ahead of time" convention (D-022). No image upload or VLM path exists anywhere in this repo.
- **Evidence**: `packages/shared/src/intellichoice_shared/bedrock.py:1-14`; the four-artifact absence sweep from REQ-21; `docs/ROADMAP.md:465`
- **Evidence type**: negative grep + code (provenance comment)
- **Verification limitations**: As REQ-21 — the web repo is excluded; the "re-opens on build" conditional is a future-state assertion and unverifiable.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### SEC-16
- **Claim ID**: SEC-16
- **Domain**: security
- **Intended state**: `terraform/modules/cloudtrail/` exists and is wired into staging: management events only, multi-region, log-file validation, 90-day bucket expiry, `aws:SourceArn` conditions.
- **Repository-observed state**: **Confirmed on every config attribute.** The module exists (`modules/cloudtrail/{main,outputs,variables}.tf`) and IS wired: `environments/staging/main.tf:743-748`, with T-01 context in the preceding comment (`:738-742`, including "GuardDuty, the other half of T-01, is deliberately NOT here"). In `modules/cloudtrail/main.tf`: `is_multi_region_trail = true` (`:152`), `include_global_service_events = true` (`:157`), `enable_log_file_validation = true` (`:159`), and **no `event_selector` block** — "management events only. Data events (S3 object-level, Lambda invoke) are the paid tier" (`:161-163`). Bucket lifecycle `expiration { days = var.log_retention_days }` plus `noncurrent_version_expiration` (`:69-75`), `log_retention_days` default **90**. Bucket hardening: public access block (`:27`), SSE (`:35`), versioning (`:47`). Both bucket-policy statements carry `aws:SourceArn` conditions (`:103`, `:128`), scoped to `AWSLogs/<account>/*` (`:118`). No GuardDuty resource anywhere in terraform.
- **Evidence**: as cited above
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; `IsLogging: true` and the 1,761-byte `.json.gz` delivery proof are runtime facts → Phase 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — config half fully confirmed, including the "still wired" evidence the ledger asked for)

#### SEC-17
- **Claim ID**: SEC-17
- **Domain**: security
- **Intended state**: D-125 deferred GuardDuty with a written reason and **tracked it to S50 A7**.
- **Repository-observed state**: **ROADMAP's S50 A7 close-out does NOT carry GuardDuty.** The S50 line reads "S50 A7 close-out (**WAF, backup-restore drill, ZAP on prod config, runbook** updated for the integrated topology)". INTEGRATION_PLAN §5's S50 row is identical and equally GuardDuty-free. The *only* GuardDuty mention in the whole of ROADMAP.md is `:1429`, inside the tranche-1 narrative describing T-01 as a gap — not a scheduling entry.
- **Evidence**: `docs/ROADMAP.md:1516-1519` (S50 A7 contents); `docs/ROADMAP.md:1429` (sole GuardDuty mention); `docs/INTEGRATION_PLAN.md:475` (S50 row); `docs/TRACEABILITY.md:737-744` (claims the tracking); `docs/SPEC.md:2868` (still requires it)
- **Evidence type**: docs
- **Verification limitations**: D-125's own body was not read; the claim under test was ROADMAP's S50 A7 content.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — **HIGH**: a required §5.30.3 control is asserted as "tracked to S50 A7" while neither ROADMAP's nor INTEGRATION_PLAN's S50 A7 scope lists it, so the deferral has no destination)

#### SEC-18
- **Claim ID**: SEC-18
- **Domain**: security
- **Intended state**: No AWS WAF resource exists.
- **Repository-observed state**: Confirmed. Case-insensitive grep for `waf` across all terraform `*.tf` returns **three comment-only hits and zero resources**: `environments/staging/main.tf:742`, `modules/alb/main.tf:3`, `modules/cloudtrail/main.tf:10`. No `aws_wafv2_web_acl`, no `aws_wafv2_web_acl_association`, no `aws_wafregional_*`, and no WAF association on the ALB or on either CloudFront distribution (`modules/cloudfront-spa-api/main.tf` has no `web_acl_id`).
- **Evidence**: as cited above; `modules/ecs-service/main.tf:165-166` (the in-process rate-limiter reference)
- **Evidence type**: negative grep (terraform config)
- **Verification limitations**: Configuration only; a WAF created outside Terraform would not be visible here → Phase 3B. The in-process rate-limiter half (`intellichoice_shared.rate_limit`) is code and was another worker's scope.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — WAF absent from configuration; SPEC §5.30.3's listing of WAF among present controls is already recorded in the ledger, and the deferral is documented in three places)

#### SEC-19
- **Claim ID**: SEC-19
- **Domain**: security
- **Intended state**: The escalation cap moved off the in-memory limiter to a shared Postgres counter; the one limit is enforced across tasks; transactionally safe.
- **Repository-observed state**: Confirmed, and the safety mechanism is an advisory lock rather than an atomic increment. Table/model: `rate_limit_events` (`packages/db/src/intellichoice_db/models/rate_limit.py`, `RateLimitEvent` with `scope`/`caller_key_hash`/`created_at` and one composite index); the module docstring records the measured defect ("**8 escalation drafts accepted from one IP against a configured 5**"). Counting: `packages/db/src/intellichoice_db/repositories/rate_limit.py:22-67` `try_consume` takes `pg_advisory_xact_lock(hashtext('scope:caller_hash'))` first (`:44-47`), then count → prune-own-expired → insert → commit, with the docstring naming the exact race ("under READ COMMITTED, two concurrent callers counting before either commits both see the pre-insert total and both pass"). It deliberately holds a **session factory, not the request session**, so the consumed attempt commits before the response. Wiring: `PostgresRateLimiter` (`services/escalation_rate_limit.py:24-50`) is installed unconditionally with no env flag — `main.py:167` and `:176`; config `email_rate_limit_max_per_window=5`, `window_s=3600.0` (`config.py:108-109`). `InMemoryRateLimiter` survives only in `routers/client_errors.py:76-78` (a different surface).
- **Evidence**: as cited above
- **Evidence type**: code
- **Verification limitations**: Concurrency correctness was read from the lock ordering, not executed; `hashtext` collisions would serialize unrelated keys (safe direction, throughput only).
- **Classification**: CONFIRMED_IN_REPOSITORY

#### SEC-20
- **Claim ID**: SEC-20
- **Domain**: privacy
- **Intended state**: T-02 — the eleven-disclosure §5.1.2 first-visit notice does **not** exist in `apps/learning-web/src`; D-129 dispositioned it as S45-builds / §6.1-track-enumerates-first, the order load-bearing; "still not built" — owned and ordered rather than assumed.
- **Repository-observed state**: **No notice component and no first-visit gate in `apps/learning-web/src`.** Full inventory: `components/{ChatViz,ConnectingPanel,ErrorBoundary,ExamTimer,JourneyBar,QuestionFigure,QuestionNavBar,QuestionStem,ReportView,RichText,SkillFocus,SubmitConfirmationModal,TutorChatPanel}.tsx` and `screens/{Attendance,BookmarkedResults,ChildSelection,DevLogin,Exam,Intervention,Results,StageTransition}Screen.tsx` — nothing named notice/disclosure/consent. A case-insensitive grep for `first.?visit|disclosure|privacy.?notice|consent` returns only forward-looking comments: `main.tsx:38` "§5.1.2's first-visit disclosures are route-aware, which is why this exists", `App.tsx:39,56,87`, and an unrelated `<details>` triangle at `StageTransitionScreen.tsx:21`. No `localStorage`/`sessionStorage` first-visit flag exists — the only `localStorage` keys are the dev token/sub/role (`App.tsx:61-63,383-399`). The referenced sibling pattern does exist in the chat app (`apps/chat-web/src/screens/LocationConsentModal.tsx`), so "the pattern exists, the learning app has no notice" is accurate today. **The §6.1 track has started and its T-02 gating deliverable is complete** — newer than the claim's temporal note: `docs/FIRST_VISIT_NOTICE.md` (237 lines, added `da2549f`, 2026-08-15) writes out all eleven disclosures as copy in two registers, each with a "True because" / "Goes false if" row; its title line reads "SPEC §5.1.2's eleven disclosures, enumerated (T-02)" and `:5-6` "**S45 transcribes this; it does not draft it**". `docs/ROADMAP.md:2148-2157` now enumerates the eleven inside the §6.1 parallel-track block. A new unresolved product question came out of it: `FIRST_VISIT_NOTICE.md:203-222` finds three of the eleven describe behaviour that does not exist and recommends shipping eight. S45 remains unbuilt inside the frozen S43–S47 block (`ROADMAP.md:1502-1504`).
- **Evidence**: `apps/learning-web/src/` inventory; `apps/learning-web/src/main.tsx:38`, `App.tsx:39,56,87`, `:61-63`; `apps/chat-web/src/screens/LocationConsentModal.tsx:1-75`; `docs/FIRST_VISIT_NOTICE.md:1-14,203-222,233-237`; `docs/ROADMAP.md:1408,1502-1504,2148-2157`; `docs/PROGRESS.md:978-982`; `docs/TRACEABILITY.md:650,652-698`. Commands: `ls -R apps/learning-web/src`, `grep -rniE "first.?visit|disclosure|privacy.?notice|consent" apps/learning-web/src apps/chat-web/src`, `git log -- docs/FIRST_VISIT_NOTICE.md`
- **Evidence type**: negative grep (component absence) + docs (artifact presence) + git history
- **Verification limitations**: Absence is proven for `apps/learning-web/src` only, per the claim's own scope; a notice served from outside the SPA bundle, or from `../IntelliChoice-web` (out of bounds), was not checked. Whether counsel review has occurred is off-repo → 3B.
- **Classification**: CONFIRMED_IN_REPOSITORY (the claim's substance holds exactly — notice absent, item owned and ordered. Drift LOW: the claim's temporal field "§6.1 track not started at writing" is superseded, the track's T-02 output having shipped 2026-08-15 while the build stays frozen-unbuilt. The eight-vs-eleven decision is already carried by the WORK-33 entry — cross-linked, no new decision row.)

#### SEC-23
- **Claim ID**: SEC-23
- **Domain**: security
- **Intended state**: LangSmith needs a PII-masking policy, retention configuration, and separate per-environment projects, expressed as configuration rather than as a required-account row.
- **Repository-observed state**: **Masking policy: configured** — `configure_langsmith()` forces `LANGSMITH_HIDE_INPUTS`/`LANGSMITH_HIDE_OUTPUTS`, with a test asserting it is not optional. **Per-environment project: configured** — `LANGSMITH_PROJECT = var.name_prefix` in terraform (i.e. `intellichoice-staging`), overriding the code's `setdefault("LANGSMITH_PROJECT", "intellichoice")`, so environment separation is real and env-driven. **Retention configuration: NOT FOUND in the repository** — no terraform, env, or code setting governs LangSmith run retention; it is a LangSmith-side account setting. Secrets themselves are ARN-only in terraform (`LANGSMITH_API_KEY` is an `aws_secretsmanager_secret` ARN; `*.tfvars` and `*.tfplan` gitignored with the reason written out).
- **Evidence**: `packages/observability/src/intellichoice_observability/langsmith_config.py:26-42`; `terraform/environments/staging/main.tf:149-178`; `.gitignore` (Terraform block)
- **Evidence type**: code + test-source + terraform config + negative grep (names only; no secret values read)
- **Verification limitations**: Retention is external to the repo and unverifiable here → 3B/external. Nothing in the repo would detect its absence.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — LOW drift: LangSmith retention has no in-repo expression at all; masking and per-env project are configured)

#### SEC-24
- **Claim ID**: SEC-24
- **Domain**: incident
- **Intended state**: On 2026-07-22 `seed_mysql.py`'s success print emitted the real RDS MySQL master password into CloudWatch Logs and the session transcript; fixed live with `render_as_string(hide_password=True)`.
- **Repository-observed state**: The fix survives, with the incident recorded at the fix site: the only print in `seed_mysql.py` is `render_as_string(hide_password=True)`, preceded by a comment naming "a real leak into CloudWatch Logs during S32/D-084's first deploy - the password was rotated immediately after". A repo-wide grep for `print(...password|secret|url|dsn|URL...)` across `scripts/`, `packages/*/src`, `apps/*/src` returns **exactly one** hit — that same redacted line. The two `hide_password=False` uses in non-test code are in `session_consolidation_cli.py`, whose docstring states "The rendered string contains the password, so it is returned for immediate use and must never be logged or printed", and the value is returned, not printed.
- **Evidence**: `packages/adapters/src/intellichoice_adapters/seed/seed_mysql.py:33-37`; `apps/learning-api/src/learning_api/services/session_consolidation_cli.py:80-85`
- **Evidence type**: code + negative grep
- **Verification limitations**: Confirms the current code shape, not the 2026-07-22 event itself or that the leaked value was rotated. The grep pattern covers `print()` with a secret-suggesting substring in the same call; a leak via `logger.info` with a differently-named variable would not appear. No secret value was read or printed.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### SEC-25
- **Claim ID**: SEC-25
- **Domain**: incident
- **Intended state**: Incident D-085 — `/dev/token` was reachable on the real staging ALB; the fix added an independent second gate rather than flipping one flag, and `/dev/token` is currently secret-gated (D-097).
- **Repository-observed state**: Confirmed, and the gate is now a **third** mechanism layered on the original two. The predicate: `settings = get_settings(); local_dev_path = settings.environment == "dev" and settings.dev_token_endpoint_enabled; return local_dev_path or staging_secret_matches(presented_secret, settings.staging_token_shared_secret)` — applied both in HTTP middleware *before routing* and again inside the handler ("defence in depth rather than a relocation of the check"). `staging_secret_matches` fails closed on an unconfigured secret and uses `hmac.compare_digest`. Terraform wires two distinct 64-char `random_password` secrets into `LEARNING_STAGING_TOKEN_SHARED_SECRET` / `CHAT_STAGING_TOKEN_SHARED_SECRET` as ARNs. `app_environment` default is now `"staging"` (`variables.tf:68-71`) and both task definitions set `*_DEV_TOKEN_ENDPOINT_ENABLED = "false"`, so the local-dev arm is closed in staging by both of its conditions. `deploy-staging.yml:503+` additionally asserts live unreachability without the secret.
- **Evidence**: `apps/learning-api/src/learning_api/main.py:346-367`; `packages/shared/src/intellichoice_shared/auth.py:111-177`; `terraform/environments/staging/main.tf:355-389,513,595`; `apps/learning-api/tests/test_stream_and_history.py:152-345` (nine gate tests incl. "404s on staging without the shared secret" and "closed is indistinguishable from an absent path")
- **Evidence type**: code + test-source + terraform config + CI config
- **Verification limitations**: "Currently secret-gated on the live ALB" is runtime and caps here. No secret value was read.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — no drift)

#### SEC-26
- **Claim ID**: SEC-26
- **Domain**: incident
- **Intended state**: Evidence of whether the two staging `/dev/token` secrets were ever rotated after the D-310 process-table exposure on 2026-08-13.
- **Repository-observed state**: **No evidence of rotation.** `git log -S"staging_token_shared_secret" -- terraform` returns exactly **one** commit ever: `168de30 S36 (AUD-L, partial): secret-gated staging token path; fix a P0 cost hole` — the original creation. The two `random_password` resources carry no `keepers`, no rotation trigger, and no `aws_secretsmanager_secret_rotation` resource exists anywhere in `terraform/`. The block comment (`main.tf:355-360`) plans deletion at S44, not rotation.
- **Evidence**: `git log -S"staging_token_shared_secret" -- terraform`; `terraform/environments/staging/main.tf:355-389`; negative grep for `aws_secretsmanager_secret_rotation` across `terraform/`
- **Evidence type**: git history + terraform config + negative grep
- **Verification limitations**: Rotation in-place would not require a repo change (it is a state/CLI action), so absence of a commit is weak negative evidence only; a console/CLI/taint rotation would leave no repo trace. Live secret version history is 3B.
- **Classification**: UNVERIFIED (adjudicated centrally — → 3B. LOW drift: no rotation mechanism is configured anywhere, so post-D-310 rotation would be out-of-band and the "bounded exposure" premise rests on a manual action with no in-repo control.)

#### SEC-32
- **Claim ID**: SEC-32
- **Domain**: open-work
- **Intended state**: The production security report was sent as one message to the production operator.
- **Repository-observed state**: **No send record exists; the most recent pointer still lists sending as an outstanding user action.** The report header carries only `**Drafted:** 2026-08-02 (S43)` with no send/recipient/confirmation field. PROGRESS's "Next session" item 4 reads "**Send the two drafted messages** (written and send-ready; the remaining step is you sending them to the right people)". Earlier PROGRESS text says "resolve before either is sent" and "drafted send-ready". DECISIONS has zero send records.
- **Evidence**: `docs/S42_SECURITY_REPORT.md:1-13`; `docs/PROGRESS.md:7726`, `:13689`, `:13703`
- **Evidence type**: docs (negative)
- **Verification limitations**: Negative evidence; a send could have occurred out-of-band and gone unrecorded.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — drift **HIGH, real-world**: two High findings against a live system sit in an unsent draft with no send-status field. One drift entry covers the unsent-report family: SEC-32, INT-13, INT-25.)

#### SEC-33
- **Claim ID**: SEC-33
- **Domain**: security
- **Intended state**: §7-R1 (production-repo compromise ⇒ new-stack impersonation) accepted as permanent, "to be signed off by the org at S42"; mitigation limited to I14's refresh check.
- **Repository-observed state**: **No org sign-off record of any kind.** The only occurrence of the obligation is the statement of it at `INTEGRATION_PLAN.md:513`; a corpus grep for `sign.off|signed off` across DECISIONS/PROGRESS/INTEGRATION_PLAN/S42_SECURITY_REPORT returns nine hits, none about R1 or any org sign-off. **No I14 refresh-check build record either** — every I14 mention is prospective and scoped to S44, inside the D-152-frozen S43–S47 block.
- **Evidence**: `docs/INTEGRATION_PLAN.md:502-517` (`:513` the obligation), `:410`, `:436`, `:466`; `docs/ROADMAP.md:1492` (S44, frozen), `:1438-1445` (freeze banner)
- **Evidence type**: docs (negative)
- **Verification limitations**: Negative evidence for both halves.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — drift **HIGH**: R1's sign-off obligation has its only occasion (S42 org interaction) frozen, and R8/R9's expiry conditions are unmonitored with the ARCHITECTURE.md copy DROPPING the expiry text. One register entry covers SEC-33, INT-22, INT-33, cross-linked to the G3/SEC-09 expiry-vs-freeze entry.)

#### SEC-34
- **Claim ID**: SEC-34
- **Domain**: authorization
- **Intended state**: The Tutor/Manager role allowlist is designed into S43/S44 work.
- **Repository-observed state**: **Present in the S43-scoped ROADMAP block as a constraint, not as a design.** ROADMAP's S43 entry carries a `⛔ Security constraint (D-153 §5, rationale updated in §7)` sub-block reproducing all three grounds verbatim and closing with "Map Student/Parent from production; gate `Tutor`/`Manager` behind an allowlist the new stack controls." The S43 header also lists "fail-closed role mapping" and "(I12)" deploy-time schema smoke probe. **No allowlist schema, storage, or admin path is specified, and the I7 unknown-role metric is named only as an id** — no I7 metric plan was found in the S43 region.
- **Evidence**: `docs/ROADMAP.md:1465-1491` (constraint at `:1482-1489`); `docs/S42_SECURITY_REPORT.md:167-170`; `docs/INTEGRATION_PLAN.md:521-522`, `:572-573`; `docs/S42_OPEN_QUESTIONS.md:36-37`
- **Evidence type**: docs
- **Verification limitations**: "Design" judged by the presence of a stated mechanism in the S43-scoped docs only; no source inspection (S43 code does not exist).
- **Classification**: CONFIRMED_IN_REPOSITORY (the constraint is present and consistently stated across four documents; LOW note: the I7 unknown-role metric has no plan text)

#### SEC-35
- **Claim ID**: SEC-35
- **Domain**: security
- **Intended state**: The two staging token secrets are Terraform `random_password` values in Secrets Manager, never handed to a human.
- **Repository-observed state**: **Confirmed, both.** `environments/staging/main.tf:361-364` `resource "random_password" "staging_token_shared_secret_learning" { length = 64, special = false }` and `:366-369` the `_chat` twin; each written to a Secrets Manager secret via `aws_secretsmanager_secret` + `aws_secretsmanager_secret_version` (`:371-389`) at names `${var.name_prefix}/learning-api/staging-token-shared-secret` and `${var.name_prefix}/chat-api/staging-token-shared-secret`; injected into the tasks as `LEARNING_STAGING_TOKEN_SHARED_SECRET` (`:513`) and `CHAT_STAGING_TOKEN_SHARED_SECRET` (`:595`) by ARN; read access granted to the execution role (`:277-278`). The same shape exists for the two JWT signing secrets (`:317-345`). Rationale matches: "Possession of a 64-char random secret is a different kind of gate" (`:354-355`), staging-only lifetime at `:358-360`. RDS rotation path also confirmed: `manage_master_user_password = true` on both engines, consumed as `:username::`/`:password::` JSON-key ARNs.
- **Evidence**: as cited above; `modules/rds-postgres/main.tf:61`, `modules/rds-mysql/main.tf:51`, `environments/staging/main.tf:507-510`, `:589-592`
- **Evidence type**: terraform config
- **Verification limitations**: Configuration only; that the values exist in Secrets Manager and that `get-secret-value` recovered them is Phase 3B. No secret value was read. Whether older "blocked on missing credential" statements were corrected in place is a docs-side check.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally)

### 3.4 COST family — 24 claims

#### COST-02
- **Claim ID**: COST-02
- **Domain**: cost-control
- **Intended state**: Only `generate_structured` + `create_embedding` exist; the other four SPEC gateway methods are dispositioned by name in the `bedrock.py:4-13` docstring; the judge is verified independently in `packages/evals`.
- **Repository-observed state**: Verified exactly as claimed. `bedrock.py:4-13` reads: "`generate_structured` and `create_embedding` are defined on `BedrockGateway` - SPEC's interface also lists `generate_stream`/`classify`/`analyze_image`, but none has a real caller yet (S18/S29 respectively; S29 was deferred, D-078)... See D-022." and continues "SPEC's separate `judge` method never got its own Protocol method either - `BedrockTask.LLM_JUDGE` (reserved since S8, unused until S30) is dispatched through the same `generate_structured` call every other task uses". The Protocol at `bedrock.py:1579-1602` declares only the two methods. `ResilientBedrockGateway` defines only `generate_structured` (`:196`) and `create_embedding` (`:396`) as public async methods. Judge routing confirmed at `packages/evals/src/intellichoice_evals/llm_judge.py:64`. `BedrockTask.VLM` exists in the enum with no caller, consistent with the S29/D-078 deferral.
- **Evidence**: bedrock.py:1-20, 1579-1602; gateway.py:196, 396; llm_judge.py:64; grep for `analyze_image|generate_stream` returning only the docstring line
- **Evidence type**: code + negative grep
- **Verification limitations**: None material.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally)

#### COST-03
- **Claim ID**: COST-03
- **Domain**: cost-control
- **Intended state**: `gateway.py:58-110` implements bounded retry, max-token ceiling, per-session budget and circuit breaker, with three named test files.
- **Repository-observed state**: All four present, but the cited line range is stale. `__init__` defaults at L82-108 (`max_retries` via `_max_retries`, `circuit_failure_threshold=5`, `circuit_cooldown_s=30.0`, `session_budget_cents=50.0`, `call_timeout_s=20.0`); circuit logic `_circuit_check`/`_record_failure`/`_record_success` at L110-134; token ceiling `_HARD_MAX_OUTPUT_TOKENS = 4000` at L78 applied at L236-243; budget check at L244-263 (and again for embeddings at L427-445); retry loop at L285+. The cited `58-110` band covers roughly the constructor only; `worst_case_cost_cents` is at **L182**, not the cited L158. All three named test files exist, `test_bedrock_gateway.py` carrying `test_timeout_raises_after_exhausting_bounded_retries` (L155), `test_circuit_breaker_opens_after_threshold_and_blocks_further_calls` (L179), `test_cost_budget_exceeded_before_any_provider_call` (L215), `test_schema_failures_alone_never_open_the_circuit` (L264), `test_a_provider_outage_still_opens_the_circuit` (L308), `test_circuit_breaker_caps_provider_calls_even_under_a_concurrent_failure_burst` (L668), `test_create_embedding_cost_budget_exceeded_before_any_provider_call` (L725).
- **Evidence**: gateway.py:78-134, 182-194, 236-263, 285-310, 427-445; `packages/adapters/tests/test_bedrock_gateway.py` (23 tests); `packages/db/tests/test_cost_reservation.py`; `apps/learning-api/tests/test_cost_reservation_estimates.py`
- **Evidence type**: code + test-source
- **Verification limitations**: Tests not executed. The max-token *ceiling* caps output only.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — mechanisms plus test files; LOW drift: TRACEABILITY's cited line ranges have drifted, now :78-134 / :182-194)

#### COST-04
- **Claim ID**: COST-04
- **Domain**: spend-accounting
- **Intended state**: `worst_case_cost_cents` (cited gateway.py:158) is the pre-flight reservation bounding a call before it is made.
- **Repository-observed state**: Present at **gateway.py:182-194** (not 158): `return self._cost_cents(model_id, 2000, min(max_output_tokens, _HARD_MAX_OUTPUT_TOKENS))`. Its docstring states it is "Public so a caller can *reserve* this amount against a per-day ceiling before" the call, and that it shares the arithmetic the session-budget check uses "so the two ceilings cannot disagree." Critically, `generate_structured` does **not** call it — it recomputes the same expression inline (`worst_case_cost = self._cost_cents(model_id, 2000, capped_max_tokens)`, L244), so the two are duplicated paths kept consistent by convention plus a test. All call sites of the public method are tests (`apps/learning-api/tests/test_cost_reservation_estimates.py:49,71,78,83,118,122`; `apps/chat-api/tests/test_turn_cost_estimate.py:59,191`). Production callers use per-surface *constants* by design: `bedrock.py:1580-1586` says `worst_case_cost_cents` is "Deliberately *not* including... in the Protocol... The per-surface estimates are constants instead, kept honest by `test_cost_reservation_estimates.py`".
- **Evidence**: gateway.py:182-194, 244; bedrock.py:1580-1586; the test call sites above; `apps/chat-api/src/chat_api/services/turn_cost.py:8`; `apps/learning-api/src/learning_api/services/report.py:83`
- **Evidence type**: code + test-source
- **Verification limitations**: The "constants bound the real worst case" invariant is asserted only by an unexecuted test.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally, with qualification — production reserves against constants validated by an unexecuted test, and the public method's only callers are tests. LOW drift: the cited line is off by ~24 lines and the claim's phrasing understates that production code does not call the function.)

#### COST-05
- **Claim ID**: COST-05
- **Domain**: spend-accounting
- **Intended state**: A measured 32.0% undercount from the omitted per-slot equation-design call (D-294); both halves now traced, pinned by a named test and re-checked by a script.
- **Repository-observed state**: The fix and both artifacts exist. `scripts/measure_spend_reconciliation.py:1-33` narrates the same causal story as the doc: run summaries totalled 1278c vs `question_validation_runs.cost_cents` 884c over the same window (368 vs 378 candidates); cause = "The equation-design call is made by `generate_authored_candidate` **once per slot, before** `_attempt_authored_candidate` - which is the function that writes the rows. So the design cost reached `RunSummary` through the caller's running total and reached no row at all." The write-path fix is visible as `_row_cost()` in `ai_pipeline.py:1608+` ("What this attempt's row should say the slot has spent so far (D-294)... Distinct from `total_cost`, which is what the *caller* is told"). The pinning test is `test_authored_pipeline.py:2468`.
- **Evidence**: measure_spend_reconciliation.py:1-33, 111; ai_pipeline.py:1600-1615; test_authored_pipeline.py:2468-2540; docs/TRACEABILITY.md:237-248
- **Evidence type**: code + test-source + docs
- **Verification limitations**: Neither the test nor the script was executed (both need a database). The historical 2026-08-12 event is corroborated only by in-repo narrative, not by row data.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — artifacts confirmed; execution is 3B. LOW drift: 31% in code/script/test vs 32.0% in docs, raw figures ≈30.8%.)

#### COST-06
- **Claim ID**: COST-06
- **Domain**: spend-accounting
- **Intended state**: The `skipped_duplicate_id` path is explicitly *not* covered by a test; the row is rolled back and the money stays attributable only to the run total.
- **Repository-observed state**: **The claim as literally worded is contradicted, and the underlying accounting gap is worse in one branch than the doc says.** (a) A test does exercise the path: `test_per_candidate_settlement_survives_a_duplicate_id` (`packages/curriculum/tests/test_authored_pipeline.py:1673`) forces a collision and asserts `summary.skipped_duplicate_id == 1`, `summary.pending == 0`, and that the already-committed row is untouched (L1710-1716). (b) Two distinct duplicate-id branches exist in `pipeline_cli.py`: the `_settle` commit-time branch (L303-312) does `summary.total_cost_cents += outcome.cost_cents` before `summary.skipped_duplicate_id += 1`, so the money *does* stay in the run total as claimed; but the `run_plan` flush-time branch (L601-618) catches `IntegrityError`, does `session.rollback()`, increments `skipped_duplicate_id`, and `continue`s — **skipping both `spend += outcome.cost_cents` (L619) and `_settle`**, because the exception destroys the `outcome`. Paid calls (`generate_structured` at `ai_pipeline.py:981`, `:1328`) precede the row flush (`create_template` at `ai_pipeline.py:2046`), so real spend on that branch reaches neither the row, `summary.total_cost_cents`, nor the budget-gating `spend` total the run-budget check at L577 reads.
- **Evidence**: `packages/curriculum/src/intellichoice_curriculum/pipeline_cli.py:295-312`, `:560-635` (esp. the `continue` at L618 preceding `spend += outcome.cost_cents` at L619), `:577`; `packages/curriculum/src/intellichoice_curriculum/ai_pipeline.py:981`, `:1328`, `:2046`; `packages/curriculum/tests/test_authored_pipeline.py:1673-1716`; `docs/TRACEABILITY.md:246-248`
- **Evidence type**: code + test-source
- **Verification limitations**: The call-ordering half was re-traced centrally (paid calls precede the flush); no run was executed, so the loss is demonstrated by code path rather than measured. D-294's own text was not read by the inspector.
- **Classification**: CONFLICT (adjudicated centrally — orchestrator-verified by direct re-read. Severity adjudicated MEDIUM, down from the inspector's HIGH: per-event loss is bounded to one slot's spend, `budget_ceiling_cents` still bounds during the call, duplicate-id collisions are rare, and the pipeline is parked (D-342). Phase 3B cannot resolve it — the evidence is repo-evident.)

#### COST-08
- **Claim ID**: COST-08
- **Domain**: cost-control
- **Intended state**: A `_spend` accumulator whose running total every downstream call site receives (not the initial value), plus a per-slot `budget_ceiling_cents`.
- **Repository-observed state**: Both present and threaded. In `ai_pipeline.py`: `spend = session_spend_cents` (L1600), `total_cost = 0.0` (L1601), and `def _spend(cost)` (L1603-1606) mutating both via `nonlocal`. Downstream call sites pass the *running* value: `session_spend_cents=spend` at L1334, L1915, L1927, L1974, `create_embedding(..., session_spend_cents=spend)` at L1871, and `session_spend_cents=spend + total` at L1251 — each followed by `_spend(cost)` (L1683, L1875, L1918, L1930, L1978). This is the AUD-L-02 shape (a ceiling passed a frozen 0.0) explicitly avoided. Per-slot ceiling: `budget_ceiling_cents: float | None = None` (L2194) with docstring at L2225, enforced at L2344-2350 (`if budget_ceiling_cents is not None and session_spend_cents + spent >= budget_ceiling_cents`), threaded at L2298. The run-level caller wires the two together: `pipeline_cli.py:592` passes `budget_ceiling_cents=plan.run_budget_cents` ("The slot may not spend past the run's own ceiling; without this the between-slot check only notices after the money is gone"), alongside the between-slot check at L577.
- **Evidence**: ai_pipeline.py:1600-1606, 1251, 1334, 1683, 1871-1978, 2190-2350; pipeline_cli.py:577, 590-592
- **Evidence type**: code
- **Verification limitations**: Reachability established by reading the threading, not by executing a run; the budget tests were not read. The `run_plan` flush-time branch noted under COST-06 means `spend` can under-count on a duplicate-id collision, which weakens the between-slot check.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — tests unexecuted where cited)

#### COST-09
- **Claim ID**: COST-09
- **Domain**: spend-accounting
- **Intended state**: Reserve the worst case in `cost_reservations` in an immediately-committed transaction before the model call, settle after, serialized by `pg_advisory_xact_lock`; unsettled reservations stay charged at estimate; the per-session gateway budget explicitly not covered.
- **Repository-observed state**: All four elements verified in `packages/db/src/intellichoice_db/repositories/cost_reservation.py`. (a) Separate connection: `def __init__(self, session_factory: async_sessionmaker)` (L43) and every method opens `async with self._session_factory() as session` (L64, L92, L102+) — bound to a factory, not a request-scoped session; wired in production at `apps/learning-api/.../dependencies.py:52` and `apps/chat-api/.../dependencies.py:110` from `request.app.state.db_session_factory`. (b) Advisory lock: `await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"{scope}:{subject_external_id}"})` (L65-68), with a docstring explaining why `INSERT ... SELECT` alone is insufficient under READ COMMITTED (L57-62). (c) Reserve-before-spend with immediate commit: sum → ceiling check → `raise CeilingReachedError` (L69-76, committing rather than rolling back to release the lock) → `session.add(row)` → `await session.commit()` → return `Reservation` (L78-85). (d) `settle(reservation_id, actual_cents)` (L87-99) sets `actual_cents`/`settled_at`, its docstring stating "Best-effort by design: a reservation that is never settled stays charged at its estimate, which over-counts rather than under-counts". Production reserve call sites: `graph/nodes.py:1470`, `services/report.py:459`, `apps/chat-api/.../routers/sessions.py:548`. The stated coverage gap is corroborated by `bedrock.py:1580-1586` keeping `worst_case_cost_cents` off the Protocol.
- **Evidence**: cost_reservation.py:42-110; dependencies.py:52 / :110; nodes.py:1470; report.py:459; sessions.py:548; `packages/db/tests/test_cost_reservation.py:59-210`
- **Evidence type**: code + test-source
- **Verification limitations**: Tests not executed; the "before the model call" ordering was confirmed at the repository API level, not by tracing each of the three call sites' statement order.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — tests unexecuted where cited)

#### COST-10
- **Claim ID**: COST-10
- **Domain**: cost-control
- **Intended state**: An input-token bound in gateway code (D-141's fix), sized against the timeout.
- **Repository-observed state**: **The input bound exists, but it is not in the gateway.** Grep for `max_input|MAX_INPUT|MAX_PROMPT|max_prompt|D-141` across `packages/adapters/.../bedrock/` and `packages/shared/.../bedrock.py` returns **zero** hits — the gateway bounds output only (`_HARD_MAX_OUTPUT_TOKENS = 4000`) and uses a hardcoded 2000-token input *assumption* for pricing (gateway.py:194, 244), an estimate not a bound. The actual fix landed at the caller, `packages/memory/src/intellichoice_memory/consolidation.py:81-114`: "AUD-F-34 (D-141): the payload had no *input* bound at all. The gateway bounds output tokens and per-run spend; nothing bounded how much went in, so one week of a load-tested student's tutor chat built a 215,355-token prompt against Haiku 4.5's 200,000-token context and every call failed - while the process exited 0." The bound is sized against the timeout as claimed: `_MAX_EVENT_TOKENS_PER_CALL = 20_000` (L104) with "**20k, and the first deployed value of 120k is why this comment is long.**" and "`bedrock_call_timeout_s` is 20 s. A 120k-token prompt does not reliably finish inside it - two calls timed out, and because `max_retries` is 2 those two calls burned 6 attempts against a `circuit_failure_threshold` of 5, so the breaker opened." Supporting constants `_CHARS_PER_TOKEN = 3.0` (L108), `_MAX_EVENT_CHARS_PER_CALL` (L109), `_MAX_CALLS_PER_STUDENT = 4` (L113); a longer job timeout at `packages/memory/src/intellichoice_memory/settings.py:17`.
- **Evidence**: consolidation.py:81-114; settings.py:17, 36; gateway.py:78, 194, 244; zero-hit grep over the bedrock adapter and shared bedrock module
- **Evidence type**: code + negative grep
- **Verification limitations**: The bound is verified for the `memory-consolidate` path only. Other potentially unbounded-input paths (RAG context assembly, tutor-chat history) were not checked, so the bound's coverage across paid callers is unestablished.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — MEDIUM drift: the D-141 bound lives in `packages/memory/consolidation.py`, sized against the timeout as claimed, NOT in the gateway; the gateway still has no input bound, so any new paid caller inherits the AUD-F-34 shape)

#### COST-11
- **Claim ID**: COST-11
- **Domain**: spend-accounting
- **Intended state**: D-400 (2026-08-17) closed the per-student/session spend-attribution question; COST-23's "still open" listing is superseded.
- **Repository-observed state**: **Two documents still carry it as open, in opposite ways.** (1) `AUDIT_2026_08_16.md:239-241` still states "Bedrock spend is attributable per day and per app but **never per student or per session**" with **no resolution marker**, while an adjacent paragraph in the same block *does* carry one (`✅ resolved 2026-08-17, D-394`) — so the file marks resolutions selectively and left this one unmarked. (2) `PROGRESS.md:11664` still reads "**Carry-over:** per-student spend attribution and the single-inbox alarm target are the last two observability items from the 08-16 audit." Both are contradicted by `ROADMAP.md:2909` (W8 ✅ done 2026-08-17, D-400) and `PROGRESS.md:250-258`.
- **Evidence**: `docs/AUDIT_2026_08_16.md:239-241` (unmarked) vs `:247-248` (marked resolved); `docs/PROGRESS.md:11664`; `docs/ROADMAP.md:2909-2914`; `docs/PROGRESS.md:250-258`; `docs/INCIDENT_RESPONSE.md:222-268`
- **Evidence type**: docs
- **Verification limitations**: `PROGRESS.md:11664` sits inside a dated session block, so it may be intentionally historical; the audit-file line is not dated in place and reads as current.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — MEDIUM: unmarked-open two days after D-400 closed it, in a file that marks the adjacent finding resolved. Refutes the audit file's open state.)

#### COST-13
- **Claim ID**: COST-13
- **Domain**: observability
- **Intended state**: The two named tests (D-393, D-400) exist and assert the described properties.
- **Repository-observed state**: Both exist with the asserted content. (1) `test_the_500_access_line_carries_a_trace_id` at `packages/observability/tests/test_request_logging.py:190` — builds a real tracer provider with `InMemorySpanExporter`, applies `FastAPIInstrumentor.instrument_app`, registers a raising handler, and calls it via `TestClient(raise_server_exceptions=False)`; the docstring states it "holds only if the server span is still active when this middleware logs, which depends on `FastAPIInstrumentor` wrapping the whole middleware stack (it patches `build_middleware_stack`)". (2) `test_a_detached_task_logs_the_trace_id_of_the_request_that_spawned_it` at `packages/observability/tests/test_background_task_trace_join.py:54` — opens `traced_span`, captures `current_trace_id()`, `asyncio.create_task`s `deferred_work` logging `"bedrock_call"`, awaits it *after* the span closed, and asserts `payload.get("trace_id") == request_trace_id` with the failure message "a background Bedrock call cannot be joined back to the request that caused it, so per-session spend attribution needs a subject field rather than a trace-id join". A third control test `test_a_task_spawned_outside_a_span_carries_no_trace_id` (~L96) pins that no stale/fabricated id is emitted.
- **Evidence**: test_request_logging.py:185-215; test_background_task_trace_join.py:40-100
- **Evidence type**: test-source
- **Verification limitations**: Neither test executed; pass status unverified. The claim's "~80% of spend" figure comes from COST-15's measurement and was not re-derived.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — tests unexecuted where cited)

#### COST-14
- **Claim ID**: COST-14
- **Domain**: spend-accounting
- **Intended state**: `student_id` is deliberately excluded from loggable path params; that spend is attributed from `cost_reservations` with `scope='student_report'`/`'tutor_chat'`; the SQL is schema-verified but not row-verified.
- **Repository-observed state**: Both halves verified. Exclusion: `LOGGABLE_PATH_PARAMS = ("learning_session_id", "chat_session_id")` at `packages/observability/src/intellichoice_observability/request_logging.py:42` — `student_id` is not in the tuple, and the filter at L85 (`{name: params[name] for name in LOGGABLE_PATH_PARAMS if params.get(name) is not None}`) is a strict allowlist, so a `student_id` path param cannot leak into the access line. Scopes: `SCOPE_STUDENT_REPORT = "student_report"` and `SCOPE_TUTOR_CHAT = "tutor_chat"` at `packages/db/src/intellichoice_db/models/cost_reservation.py:28-29`, used in production at `routers/students.py:407`, `services/report.py:460`, `graph/nodes.py:1471`. The `cost_reservations` model carries `subject_external_id`, the per-student attribution key the doc's SQL groups by.
- **Evidence**: request_logging.py:15, 42, 85; models/cost_reservation.py:28-29; students.py:407; report.py:460; nodes.py:1471
- **Evidence type**: code
- **Verification limitations**: The doc's SQL was not run and, per the claim's own framing, is not row-verified against staging — so "attributed per student per day" is verified as *schema-supportable*, not as producing correct totals. `docs/INCIDENT_RESPONSE.md:262-278` was not compared column-by-column against the model.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — verified at the level the claim asserts: schema-verified, not row-verified)

#### COST-16
- **Claim ID**: COST-16
- **Domain**: alerting
- **Intended state**: An AWS Budget alarm exists; `bedrock_session_budget_cents`, `bedrock_circuit_failure_threshold`, `bedrock_circuit_cooldown_s` exist; the response levers are lowering the budget or scaling `desired_count` to 0.
- **Repository-observed state**: All confirmed. `aws_budgets_budget.monthly` exists with two notifications (ACTUAL > 80%, FORECASTED > 100%) emailing `var.notification_email`, `monthly_budget_usd` default 20. `bedrock_session_budget_cents = 50.0`, `bedrock_circuit_failure_threshold = 5`, `bedrock_circuit_cooldown_s = 30.0` are declared in both app Settings and in six package settings modules (evals, memory, curriculum, youtube, knowledge, …). `desired_count` is a real terraform variable (module default 1; learning-api 2) — so scaling to 0 is an available lever, but `desired_count` is in `ignore_changes` and autoscaling owns it once the service exists.
- **Evidence**: `terraform/modules/observability/main.tf:1-23`; `terraform/modules/observability/variables.tf:5-18`; `apps/learning-api/src/learning_api/config.py:119-121`; `apps/chat-api/src/chat_api/config.py:80-82`; `terraform/environments/staging/main.tf:443-447`
- **Evidence type**: terraform config + code
- **Verification limitations**: Whether the budget notification is actually delivering is 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — LOW drift: the runbook lever "scale `desired_count` to 0" is not literally effective on a live service (`ignore_changes` + autoscaling min); the operative knob is `autoscaling_min_capacity`. Runbook-accuracy note against INCIDENT_RESPONSE and the COST playbook.)

#### COST-17
- **Claim ID**: COST-17
- **Domain**: alerting
- **Intended state**: P1-5 — a `$.event="client_error"` metric filter plus an alarm now exist (D-377); D-419 routes client errors to the page channel.
- **Repository-observed state**: Fully confirmed. `aws_cloudwatch_log_metric_filter.client_errors` — `for_each = var.log_group_names`, pattern `{ $.event = "client_error" }`, metric `ClientErrors`, `default_value = 0`. `aws_cloudwatch_metric_alarm.client_errors` — per service, `period = 900`, `Sum > var.client_error_alarm_threshold` (default **0**), `treat_missing_data = "notBreaching"`, **routed to `aws_sns_topic.alerts`** (the page channel), matching D-419's inventory. Both apps have the reporting half (`apps/{learning-api,chat-api}/src/*/routers/client_errors.py` plus tests).
- **Evidence**: `terraform/modules/observability/app_events.tf:28-68`; `terraform/modules/observability/variables.tf:165-173`; `apps/learning-api/src/learning_api/routers/client_errors.py`
- **Evidence type**: terraform config + code
- **Verification limitations**: Deployed existence of the filter and alarm is 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — supersession of the finding verified at config level; no drift)

#### COST-18
- **Claim ID**: COST-18
- **Domain**: observability
- **Intended state**: (audit finding, since asserted closed at batch granularity) All four enabled scheduled jobs reported only via `print()`; a structured-event query returned nothing but the deploy-time loader.
- **Repository-observed state**: **The finding is closed in code and the closure is itemized in-code as D-377.** All four entrypoints now call `report_job_complete(...)` immediately after their `print()`, emitting a structured record whose message becomes the JSON `"event"` field with counts as `extra` fields, keyed by a `job` dimension that is deliberately the verbatim Terraform job key. The `print()` calls are retained on purpose (for humans running jobs by hand), so "plain print()" is still literally true — but it is no longer the *only* output.
- **Evidence**: `apps/learning-api/src/learning_api/services/session_consolidation_cli.py:174`; `apps/learning-api/src/learning_api/services/tutor_chat_purge_cli.py:55` with `:53-54` ("The `print` above is for a human running this by hand; it is not a number anything can query."); `apps/learning-api/src/learning_api/services/retention_purge_cli.py:104-106`; `packages/memory/src/intellichoice_memory/consolidate_cli.py:161-172` ("a staging run on 2026-08-16 added 0 facts, dropped 3,181 events over the call cap and spent 14.11 cents"); `packages/observability/src/intellichoice_observability/scheduled_jobs.py:58-63`, `:39-43`; `packages/observability/src/intellichoice_observability/logging_config.py:136`
- **Evidence type**: code
- **Verification limitations**: The audit's second half — "confirm a structured query now returns job lines" — is **not verifiable read-only**: it needs a CloudWatch Logs Insights query against the deployed ops-task log group (3B). `report_job_complete` swallows all exceptions by design, so a silent reporting failure would leave only the `print()`, and that behaviour is untestable here. The literal `event=` `key=value` form is not used — the field is `"event"` inside a JSON record.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the D-377 fix is itemized in code and the ledger's batch-granularity uncertainty is resolved. LOW residual: the fifth job, `checkpoint_retention_cli`, reports via `print` only and is unscheduled.)

#### COST-19
- **Claim ID**: COST-19
- **Domain**: alerting
- **Intended state**: P1-7 — one heartbeat alarm per job with `treat_missing_data = "breaching"`.
- **Repository-observed state**: Confirmed — **four** heartbeat alarms, generated by `for_each = toset(var.nightly_job_events)` where the staging call passes exactly four job names: `session-consolidate`, `chat-purge`, `retention-purge`, `memory-consolidate` (`youtube-sync` deliberately excluded because `enabled = false`). Posture, quoted: `resource "aws_cloudwatch_metric_alarm" "nightly_job_heartbeat" { for_each = toset(var.nightly_job_events); comparison_operator = "LessThanThreshold"; period = 172800 # two days, so one missed night is a blip and two is an alarm; threshold = 1; treat_missing_data = "breaching"; dimensions = { job = each.key }; alarm_actions = [aws_sns_topic.alerts.arn]`. Backed by the matching `nightly_jobs` metric filter (`{ $.event = "<name>_job_complete" }`, dimensioned on `$.job`, deliberately **no** `default_value` so a job that never ran emits no series). Routed to the page channel. `var.nightly_job_events` default is `[]` in the module — the four come from the environment.
- **Evidence**: `terraform/modules/observability/app_events.tf:169-223`; `terraform/environments/staging/main.tf:772-782`; `terraform/modules/observability/variables.tf:195-202`
- **Evidence type**: terraform config
- **Verification limitations**: Whether the four alarms exist in AWS and are in OK is 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — the ledger's "posture unverified" is resolved at config level; no drift)

#### COST-20
- **Claim ID**: COST-20
- **Domain**: observability
- **Intended state**: (as closed) P1-8 — the counter is incremented before the except-return, and an `"unknown"` label is actually emitted.
- **Repository-observed state**: **Fixed.** The increment now sits above the `return` inside the except block, it is the `"unknown"` label, and a `logger.warning` was added on the same path. The audit's original defect is preserved as an in-code narrative: `except Exception as exc:  # SPEC §5.29: MySQL attendance failure -> block start` / "**The `return` used to sit above the counter, so a broken gate went silent instead of spiking** (D-377). `"unknown"` was declared in the metric's labelnames and emitted nowhere in the repo" / `ATTENDANCE_CHECKS.labels(result="unknown").inc()` / `logger.warning("attendance_check_failed", ...)` / `return {"phase": "error", ...}`. Success path at `:397` `ATTENDANCE_CHECKS.labels(result="blocked" if gate.blocked else "present").inc()`. Repo-wide grep for `ATTENDANCE_CHECKS` finds exactly three non-test sites: the declaration (`packages/observability/src/intellichoice_observability/metrics.py:26-30`, `labelnames=("result",)  # "present" | "blocked" | "unknown"`) and these two increments.
- **Evidence**: `apps/learning-api/src/learning_api/graph/nodes.py:379-395`, `:397`; `packages/observability/src/intellichoice_observability/metrics.py:26-30`
- **Evidence type**: code + exhaustive grep
- **Verification limitations**: `"unknown"` is emitted only on the adapter-exception path, not when `check_attendance_gate` legitimately returns `AttendanceStatus.UNKNOWN` — that case increments `result="blocked"`. So the routine D-152 §2 path is still not separable from a recorded absence; only adapter failure is. No alarm on the metric was verified.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the D-377 fix is itemized in code. LOW drift: `result="unknown"` means adapter-threw; a genuine `AttendanceStatus.UNKNOWN` block counts as "blocked", so the metric still cannot separate the routine path from an absence.)

#### COST-21
- **Claim ID**: COST-21
- **Domain**: alerting
- **Intended state**: P1-10 — 22 product KPIs bridged, zero alarms on any; against the closure claim of "four new application alarms reading OK" and PROGRESS's `sessions_completed_floor` not deployed.
- **Repository-observed state**: **The configured-but-absent finding stands at config level.** Two KPI-adjacent alarms were added (`client_errors`, `background_failures`) plus four job heartbeats; the only alarm on a *product KPI metric* is `sessions_completed_floor` (`metric_name = "learning_sessions_completed_total"`), and its instance count is `var.daily_completed_sessions_floor > 0 ? 1 : 0`. The variable's **default in `variables.tf` is `0`**, and the staging module call **also explicitly sets `daily_completed_sessions_floor = 0`** with the reason written out ("Staging traffic is synthetic ... Left at 0 (disabled) rather than guessed at"). No other setter exists (grep across `terraform/**.tf` returns only the variable, the guard, and that one assignment). So zero product-KPI alarms are instantiated by the configuration; `qa_answers_total` has no alarm at all.
- **Evidence**: `terraform/modules/observability/app_events.tf:130-157`; `terraform/modules/observability/variables.tf:185-193`; `terraform/environments/staging/main.tf:783-787`
- **Evidence type**: terraform config (default + explicit environment assignment)
- **Verification limitations**: Live alarm enumeration is 3B, but the count guard makes the config-level answer determinate: the resource cannot exist.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the "zero product-KPI alarms instantiated" state is provable from config alone. **MEDIUM drift**: AUDIT_2026_08_16's "all 10 P1s closed / four new application alarms reading OK" is not reconcilable with P1-10 at config level, since the one alarm answering P1-10's own suggested fix is guarded to zero instances by two independent settings and no document records raising it. Weakens the Phase-2 "P1s all closed" claim family. Cross-linked with COST-25.)

#### COST-22
- **Claim ID**: COST-22
- **Domain**: alerting
- **Intended state**: (fix) Pre-initialise the labels at import so the `qa_service_degraded_total` series exists before the first outage.
- **Repository-observed state**: **Not fixed.** There is exactly one metrics module in the repo and it contains no import-time `.labels()` call for any labelled counter. `QA_SERVICE_DEGRADED = Counter("qa_service_degraded_total", "Turns answered with the temporarily-unavailable message after a provider failure", labelnames=("stage",),  # "scope_guard" | "document_qa_retrieval" | "calendar_retrieval")` is declared with three documented `stage` values and touched only at one runtime site inside the degradation handler (`apps/chat-api/src/chat_api/graph/nodes.py:271`), so no series exists until a provider actually fails. `find -name metrics.py` (excluding node_modules/.venv) returns only the one file. Grep of every `.labels(` call site across `apps/chat-api/src`, `apps/learning-api/src`, `packages/observability/src` returns 21 hits, all inside functions/handlers; none at module scope; no `preinit`/`pre_init`/warm-up loop exists. `grep -rn "qa_service_degraded" infra/` returns nothing.
- **Evidence**: `packages/observability/src/intellichoice_observability/metrics.py:85-89`; `apps/chat-api/src/chat_api/graph/nodes.py:271`; the exhaustive negative greps above
- **Evidence type**: code + exhaustive negative grep
- **Verification limitations**: Deployed CloudWatch alarms were not enumerated — only the Terraform source. The same gap applies to every other labelled counter (`ATTENDANCE_CHECKS`, `QA_ANSWERS`, `SSE_RELAY_FAILURES`, …), so this is a module-wide pattern rather than one metric's oversight.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the finding STILL HOLDS, resolving the ledger's UNKNOWN as not-fixed. MEDIUM drift: no labelled counter in the repo pre-initialises label sets, so every low-frequency labelled KPI is unalarmable until first occurrence.)

#### COST-23
- **Claim ID**: COST-23
- **Domain**: alerting
- **Intended state**: SUPERSEDED — "all 26 alarms delivered to a single email address" is superseded by the two-topic split.
- **Repository-observed state**: The single-inbox state is superseded **in configuration**: two SNS topics exist (`${prefix}-alerts`, `${prefix}-alerts-info`), each with its own email subscription. But delivery is still single-address by default — the info subscription endpoint is `coalesce(var.informational_notification_email, var.notification_email)` and `informational_notification_email` has `default = null` with no setter in the staging module call. So topic-level routing is split while the mailbox is still one address. Alarm→topic routing is complete: 15 alarm resources in the module (8 in alarms.tf, 3 in main.tf, 4 in app_events.tf) → ~30 instances at staging's cardinality, every one carrying `alarm_actions`, none carrying both topics. The audit's "26" is a pre-D-377 count and does not match today's config.
- **Evidence**: `terraform/modules/observability/main.tf:45-73`; `terraform/modules/observability/variables.tf:20-27`; `terraform/environments/staging/main.tf:750-836`
- **Evidence type**: terraform config
- **Verification limitations**: `terraform.tfvars` was not read, so `informational_notification_email` could be set there; live subscription state (including COST-26's PendingConfirmation) is 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — LOW drift: the topic-layer split is real; the inbox is still single-address by default, as the module's own comment concedes)

#### COST-24
- **Claim ID**: COST-24
- **Domain**: alerting
- **Intended state**: D-401 — a second SNS topic; three alarms moved on a narrow rule; the page channel the default for anything new; a test failing on an unrouted alarm or a quietly-moved outage alarm.
- **Repository-observed state**: All four elements present, and **the test exists** at `packages/observability/tests/test_alarm_severity_routing.py` — a pytest that *parses* the terraform rather than planning it ("following `test_deployed_route_admission_parity.py`'s precedent (D-385) ... it runs in CI where `terraform plan` cannot"). Three controls: `test_every_alarm_notifies_exactly_one_severity_channel` (asserts `topics` non-empty, `⊆ {alerts, alerts_info}`, `len == 1`, plus a `len(alarms) >= 15` parser-drift guard); `test_the_quiet_channel_is_exactly_the_reviewed_list` (bidirectional equality against a hard-coded `_INFORMATIONAL` set); `test_the_five_hundred_and_spend_alarms_are_never_quiet` (non-vacuity control naming `target_5xx`, `rds_free_storage`, `bedrock_circuit_open`, `bedrock_spend_spike`). `_INFORMATIONAL` is exactly `{langsmith_ingest_failed, capacity_above_floor, sessions_completed_floor}` — the three alarms moved. Page-by-default holds by construction: there is no default routing, and an unrouted alarm fails the test.
- **Evidence**: `packages/observability/tests/test_alarm_severity_routing.py:1-106`; `terraform/modules/observability/main.tf:31-73`; `terraform/modules/observability/alarms.tf:76-83`
- **Evidence type**: terraform config + test-source
- **Verification limitations**: "Applied per D-419" is live state → 3B. The test was not executed.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — topics, three moved alarms, page-by-default-by-construction and the terraform-parsing routing test all exist; applied-ness is 3B. No drift.)

#### COST-25
- **Claim ID**: COST-25
- **Domain**: alerting
- **Intended state**: `sessions_completed_floor` is not deployed because its `count` is gated on `daily_completed_sessions_floor > 0` and the variable is 0 — the configured alarm count and the deployed alarm count are not the same number.
- **Repository-observed state**: Confirmed twice over, and **the test file itself documents it**: `# **Configured, not deployed** (found by a terraform plan for D-406): its count is gated on daily_completed_sessions_floor > 0 and that variable is 0, so this alarm is absent from state. This test asserts the configuration, which is the right subject - but the deployed alarm count and the configured one are not the same number.` The guard is `count = var.daily_completed_sessions_floor > 0 ? 1 : 0`; the variable default is `0` in `variables.tf:192` **and** the environment passes `0` explicitly at `main.tf:787`. Of the three `_INFORMATIONAL` alarms, only `langsmith_ingest_failed` (×2 services) and `capacity_above_floor` (×2 floors) can instantiate — matching "only two existed in staging".
- **Evidence**: `packages/observability/tests/test_alarm_severity_routing.py:34-41`; `terraform/modules/observability/app_events.tf:131`; `terraform/modules/observability/variables.tf:185-193`; `terraform/environments/staging/main.tf:783-787`
- **Evidence type**: terraform config + test-source (in-repo comment as independent corroboration)
- **Verification limitations**: None needed for the config question — the count guard is decidable from config; deployed enumeration would only confirm it. The test was not executed.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — still holds; no setter raises the variable anywhere in the repo. No separate drift: this IS the evidence against COST-21, and the two are cross-linked.)

#### COST-27
- **Claim ID**: COST-27
- **Domain**: observability
- **Intended state**: LangSmith Cloud with `configure_langsmith()` forcing `LANGSMITH_HIDE_INPUTS/_OUTPUTS=true` (a test asserts it is not optional), so only node structure and timings leave; D-242 added `LangSmithIngestFailed` per service after the leg 403'd silently.
- **Repository-observed state**: `configure_langsmith()` no-ops without `LANGSMITH_API_KEY`, and when a key is present it sets `LANGSMITH_TRACING=true`, `setdefault`s the project, and **unconditionally assigns** `LANGSMITH_HIDE_INPUTS`/`LANGSMITH_HIDE_OUTPUTS = "true"` (assignment, not `setdefault` — so an env var cannot opt out). The docstring gives the reason: env-var-driven tracing "only supports the boolean form", and there is "no contractually-reviewed basis yet for judging any subset ... 'safe'". The test asserts it with SPEC quoted inline. The per-service alarm and metric filter both exist and are `for_each = var.log_group_names`, keyed on `$.logger = "langsmith.client"`, threshold 10 over 900s, routed to `alerts_info` (D-401's informational channel, deliberately not the page channel). `langsmith_correlation_metadata()` supplies `metadata.otel_trace_id` and returns `{}` rather than a null-valued key.
- **Evidence**: `packages/observability/src/intellichoice_observability/langsmith_config.py:26-42`; `packages/observability/tests/test_langsmith_config.py:39-40` "SPEC §5.32.1: 'LangSmith Cloud with complete PII masking' - not optional"; `terraform/modules/observability/dashboard.tf:112-125`; `terraform/modules/observability/alarms.tf:56-80`
- **Evidence type**: code + test-source + terraform config
- **Verification limitations**: Test unexecuted; terraform not planned or applied, so "the alarm exists per service" is confirmed in configuration only. `HIDE_INPUTS` is a LangSmith-client-side flag — the repo cannot show what the SaaS actually received. The module's docstring notes SPEC's self-hosted-vs-cloud contractual review still needs doing.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally)

#### COST-28
- **Claim ID**: COST-28
- **Domain**: cost-control
- **Intended state**: NAT and tracing are both gated so the gateway cannot be left billing after the feature is off; D-406 made the NAT follow its consumers.
- **Repository-observed state**: The consumer-keyed gating is in configuration exactly as claimed, and the claim's *own wording* is now stale in one respect — NAT is keyed to a **map of two consumers**, not to `langsmith_tracing_enabled`: `private_egress_consumers = { langsmith_tracing = var.langsmith_tracing_enabled, youtube_sync = var.youtube_sync_enabled }` / `needs_private_egress = anytrue(values(local.private_egress_consumers))`, consumed as `nat_gateway_enabled = local.needs_private_egress`. The comment records the trap D-406 closed (`youtube-sync` runs private with `assign_public_ip = false` and the YouTube Data API has no VPC endpoint). Current defaults: `langsmith_tracing_enabled = true`, `youtube_sync_enabled = false` → `needs_private_egress = true` → NAT **enabled by configuration**. `scheduled-jobs/main.tf:121` cross-references the same map. X-Ray is on a VPC endpoint gated by `enable_otel_tracing`, so LangSmith remains the only general-internet consumer today.
- **Evidence**: `terraform/environments/staging/main.tf:100-138`; `terraform/environments/staging/variables.tf:163-189`; `terraform/modules/scheduled-jobs/main.tf:121`
- **Evidence type**: terraform config
- **Verification limitations**: Whether a NAT gateway actually exists in AWS (D-419's "absent from the plan entirely") and the $33/mo idle-NAT note are live/state facts → 3B. tfvars was not read and could override either flag.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — LOW drift: docs say NAT is "gated on `langsmith_tracing_enabled`" while config has been consumer-keyed since D-406, so the documented condition is narrower than the implemented one. NAT existence → 3B.)

#### COST-29
- **Claim ID**: COST-29
- **Domain**: cost-control
- **Intended state**: Confirm task size and count are unchanged before reusing the D-136 price table as current.
- **Repository-observed state**: **Task count unchanged; task size changed.** learning-api is still pinned at two tasks (`desired_count = 2`, `autoscaling_min_capacity = 2`, with `capacity_floors.learning-api.min_capacity = 2`), matching "measured on staging at a pinned 2 tasks". But the task is now `cpu = 512 / memory = 1024`, and the config's own comment identifies the measurement as having been taken on a smaller task: "AUD-F-28 (D-122): this service is CPU-bound - a measured sweep on the old **256/512 task** showed throughput pinned at ~5.8 req/s from 10 concurrent sessions upward" ... "at 256 CPU units the p95 <= 3s promise held only to ~8 concurrent sessions. 512 units x 2 tasks is 4x that." chat-api meanwhile runs on module defaults (cpu 256 / memory 512 / desired 1, floor 1), so the two services are not the same size at all.
- **Evidence**: `terraform/environments/staging/main.tf:423-447`, `:517-556`, `:819-835`; `terraform/modules/ecs-service/variables.tf:53-69,187-191`; `docs/ARCHITECTURE.md:254-283`
- **Evidence type**: terraform config + docs
- **Verification limitations**: Live task size and count are 3B; whether D-134/D-136's arms were run on learning-api specifically at 256 is asserted by the terraform comment, not re-measured.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — **MEDIUM drift**: the D-136 price table's per-task columns were measured at 256 CPU and `ARCHITECTURE.md:254-283` quotes them as current without the AUD-F-28 resize caveat the terraform carries, so reusing the table today under-states capacity per task)

### 3.5 TEST family — 23 claims

#### TEST-01
- **Claim ID**: TEST-01
- **Domain**: traceability
- **Intended state**: D-129 states the criterion-1 reading (*nothing is undecided*, not *nothing is missing*).
- **Repository-observed state**: **Confirmed verbatim in D-129 §4.** The heading reads "criterion 1 met by writing the sentence", and §4 ("Criterion 1: the sentence, and what claiming it does not mean") states: "**Criterion 1 is therefore met, on the same terms as criterion 2 (D-123): nothing is undecided, which is weaker than nothing is missing.** T-02 is scheduled, not shipped." TRACEABILITY:110-111 and ROADMAP:1412 both carry the same sentence.
- **Evidence**: `docs/DECISIONS.md:6897` (D-129 heading), `:6979` (§4 heading), `:6990-6991` (the reading); `docs/TRACEABILITY.md:100-111`; `docs/ROADMAP.md:1412`
- **Evidence type**: docs
- **Verification limitations**: The second half of the ledger's evidence request ("no §5 section added since lacks a verdict") is covered under TEST-07, not here.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### TEST-02
- **Claim ID**: TEST-02
- **Domain**: verification-method
- **Intended state**: "Unverified counts as not traced" is the binding evidence rule, and sampled traced rows each cite a test that exists.
- **Repository-observed state**: The rule is stated as claimed, and all five sampled tranche-1 rows cite test artifacts that exist — 14 of 14 cited files present, both cited function names present. Row 1 (PII floor): `test_schema_purity.py` ✓ with `test_no_model_has_a_pii_column_name` ✓, `test_bedrock_payload_pii_floor.py` ✓, `test_tracing.py` ✓ with `test_sse_token_query_string_is_redacted_before_export` ✓, `scripts/scan_logs_pii.py` ✓. Row 2 (deterministic core): `test_exam_policy.py`, `test_mastery_bootstrap.py`, `test_report.py`, `test_exam_flow_determinism.py` ✓. Row 3 (authorization): `packages/db/tests/test_rag_search.py`, `apps/chat-api/tests/test_role_access.py` ✓. Row 4 (interrupt approval): `test_learning_graph_routes.py`, `test_calendar_action.py`, `test_admin_escalation.py` ✓. Row 5 (fail closed): `apps/learning-api/tests/test_auth_and_attendance.py` ✓.
- **Evidence**: rule at `docs/TRACEABILITY.md:17-18` "A row is **traced** only when it cites both an implementation location and a test that would fail if the requirement broke. Anything else is **unverified**, and unverified counts as *not traced*."; the sampled rows above
- **Evidence type**: test-source (existence) + docs
- **Verification limitations**: Existence-only per instruction — it was not verified that any cited test *would fail if the requirement broke*, which is the rule's actual substance. Row 5's implementation citation (`attendance.py:71-80`) is stale (function now at 96-127). Row 3 correctly self-reports §7-R8 as "a **dispositioned gap, not a traced requirement**".
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — as sampled: 5/5 rows' artifacts exist; "would fail if broken" is unverifiable without execution. No new drift beyond line-cite staleness.)

#### TEST-04
- **Claim ID**: TEST-04
- **Domain**: verification-method
- **Intended state**: The *structural* verdict is fenced — it requires (a) a citable artifact location and (b) something mechanical that fails if the artifact disappears; with no mechanism it is a gap, not a fourth verdict (`docs/TRACEABILITY.md:43-45`). The six structural sections' named mechanisms must exist.
- **Repository-observed state**: All six rows checked against `docs/TRACEABILITY.md:618-627`. (1) **§5.3** (`:622`) artifact `docs/ARCHITECTURE.md` **exists**; mechanism declared "nothing mechanical — **descriptive**", consistent with the fence. (2) **§5.27** (`:623`) artifact "**31** `extra="forbid"` models"; mechanism "`make typecheck` (pyright, 0 errors) in CI's `lint-typecheck-test`" — **mechanism exists** (`Makefile:129-130` `typecheck:` → `uv run pyright`; `.github/workflows/ci.yml:9` job `lint-typecheck-test` with `:85 run: uv run pyright` and `:88 run: uv run pytest`), and strictness pinning exists at `packages/shared/tests/test_bedrock_payload_pii_floor.py:26-32` ("`test_every_bedrock_payload_is_governed_by_one_regime` fails on a *new payload class*"). **The count is stale**: `model_config = ConfigDict(extra="forbid")` now appears **41** times in non-test source (bedrock.py 35, `curriculum/adjudications.py` 2, `curriculum/authored_bank.py` 2, `adapters/bedrock/smoke_cli.py` 2), not 31. **Mechanism-strength caveat**: pyright does not fail if an `extra="forbid"` is deleted — only the Bedrock-payload subset is pinned by tests, so clause (b) holds for Bedrock payloads and not for the other six models. (3) **§5.34** (`:624`) all named artifacts exist (`apps/learning-api/Dockerfile`, `apps/chat-api/Dockerfile`, `terraform/` 13 modules + `environments/staging`, all three workflow files), and "CI's four jobs" is accurate — `ci.yml` defines exactly four (`lint-typecheck-test:9`, `learning-web:90`, `chat-web:119`, `e2e-typecheck:151`). (4) **§5.35** (`:625`) artifact `.env.example` **exists** (4,893 bytes, 25 `=` lines); mechanism "app startup config validation" exists in form — `apps/learning-api/src/learning_api/config.py:9` `class Settings(BaseSettings)` with a `@model_validator(mode="after")` at `:39`. (5) **§5.36** (`:626`) artifact "the stack as built"; mechanism "nothing mechanical — **descriptive**" — consistent with the fence, though the artifact is not a citable location, so clause (a) is also weak, which the row concedes. (6) **§5.2.1** (`:627`) **confirmed**: `deploy-staging.yml:118` learning-api, `:135` chat-api, `:651` learning-web, `:659` chat-web, `:667/:672` S3 sync + CloudFront invalidate for each — exactly two APIs and two SPAs, no fifth unit. The fence's own bookkeeping is honoured at `:629-633`, recording §5.3 and §5.36 as descriptive rather than passing them as structural.
- **Evidence**: `docs/TRACEABILITY.md:43-51,618-633`; `Makefile:129-130`; `.github/workflows/ci.yml:9,75,82,85,88,90,119,151,169`; `.github/workflows/deploy-staging.yml:118,135,651,659,667,672`; `apps/{learning-api,chat-api}/Dockerfile`; `.env.example`; `apps/learning-api/src/learning_api/config.py:9,39`; `packages/shared/tests/test_bedrock_payload_pii_floor.py:1-32`; `terraform/modules/`, `terraform/environments/staging/`. Commands: `grep -rc 'model_config = ConfigDict(extra="forbid")' apps packages --include="*.py"`, `grep -n "^  [a-z-]*:" .github/workflows/ci.yml`, `ls apps/*/Dockerfile`
- **Evidence type**: docs + CI config + code + test-source (existence and content only)
- **Verification limitations**: No tests or CI executed — mechanism *existence* verified, not that any of them currently fails when the artifact is removed. "The deployed topology itself" (§5.3) and container-startup failure on a missing env var (§5.35) are runtime facts → 3B.
- **Classification**: PARTIALLY_IMPLEMENTED (six of six named artifacts exist and four of six name a mechanism that exists; two rows are declared descriptive by design, consistent with the fence. Drift LOW: `TRACEABILITY:623`'s "31" is now 41 in non-test source — refuting the count as stated — and the row's pyright mechanism protects only the Bedrock-payload subset, so clause (b) is partially met.)

#### TEST-05
- **Claim ID**: TEST-05
- **Domain**: traceability
- **Intended state**: SPEC §5.3 and §5.36 are recorded descriptive, requiring a human re-read whenever the architecture changes.
- **Repository-observed state**: **Multiple qualifying architecture changes landed after tranche 6, and no re-read record exists.** Post-2026-07-30 architecture changes recorded in ROADMAP/DECISIONS: D-334/D-335 (SSE bus replaced by Postgres `LISTEN`/`NOTIFY` fan-out, 2026-08-15), D-349 (same relay for chat-api), D-406/W14 (NAT gateway topology moved, 2026-08-18), D-393/D-394. TRACEABILITY.md was in fact edited on 2026-08-17 (commits `2dd9e7e`, `7285951`) — the §5.32 row was updated for D-393/D-394 — but **the §5.3/§5.36 descriptive rows were not touched and no re-read is recorded**. A corpus grep for re-read records against those two sections returns only the two places that *state the obligation*.
- **Evidence**: `docs/TRACEABILITY.md:45-47`, `:622`, `:626-633` (obligation only); `docs/ARCHITECTURE.md:610-631`; `docs/ROADMAP.md:3026`; `git log` for `docs/TRACEABILITY.md` → `7285951` (2026-08-17), `2dd9e7e` (2026-08-17)
- **Evidence type**: docs + git history
- **Verification limitations**: "Architecture change" judged from ROADMAP/DECISIONS session titles; whether D-334/D-406 rise to the threshold the clause intends is not defined anywhere.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — MEDIUM: the owed human re-read never fired across ≥3 qualifying architecture changes, while §5.36 is independently known stale)

#### TEST-06
- **Claim ID**: TEST-06
- **Domain**: traceability
- **Intended state**: The launch-scope exclusion table's three owning decisions say what the table attributes to them.
- **Repository-observed state**: **Two of three confirmed cleanly; one attribution has no textual basis and one is thin.** **D-004** — heading "Defer EKS/multi-account AWS; launch on a simpler footprint (accepted, decided at S32 2026-07-22)"; body "Spec §5.33 prescribes AWS Organizations (3 accounts), EKS across 3 AZs...". Supports "EKS-only concepts" generically, but **"Pod Security Standards" and "NetworkPolicy" do not appear in D-004** — the row is an inference, not a quotation. **D-078** — "S29 (multimodal solution images) deferred, not built (accepted, 2026-07-20)"; body cites §5.1.4 and §5.17.2. **`6.19` appears nowhere in DECISIONS.md** (only `SPEC.md:3968` and `ROADMAP.md:466`), so the "§6.19 Phase 18 (D-078)" attribution has no supporting text in D-078. **D-087** — heading is about per-IP rate limiting, but the body does carry the WAF deferral ("in-memory stopgap until a real WAF exists, not a replacement for one; WAF itself was deferred this session"). **However, "S50" and "A7" appear nowhere in D-087** — the "tracked to S50 A7" half is not in the decision (the same defect class as SEC-17).
- **Evidence**: `docs/TRACEABILITY.md:55-68`; `docs/DECISIONS.md:29-36` (D-004); `:2025-2035` (D-078); `:2883-2896` (D-087, WAF at `:2895`)
- **Evidence type**: docs
- **Verification limitations**: Only the opening ~80-100 lines of each decision block were read, not each block in full; a later addendum could carry the missing strings.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — MEDIUM: the exclusion table attributes specifics to decisions that do not contain them, and the table is the denominator of the 37-of-37 claim)

#### TEST-07
- **Claim ID**: TEST-07
- **Domain**: traceability
- **Intended state**: All 37 launch-scope §5 sections carry a verdict.
- **Repository-observed state**: **Count sustained at 37, but only by counting a scope-excluded section.** Every top-level section §5.0 through §5.36 (= 37) receives a verdict, via 17 `### §5.x` headings plus tranche-1 rule coverage plus tranche 6's traced/structural tables. §5.20 and §5.23 have zero standalone mentions and are covered only by the ranged headings `### §5.19–§5.21` and `### §5.22–§5.24`. **The arithmetic problem:** the scope section states "§5 has **37 top-level sections** (§5.0–§5.36)" and then excludes "§5.17 Multimodal solution images (**all of it**)" — leaving 36 launch-scope top-level sections. The Status line nonetheless claims "37 of 37 **launch-scope** sections". §5.17 does carry a verdict ("**Dispositioned** — the feature does not exist", tranche 1 rule 8), so 37 is reachable only by counting the excluded section's disposition inside the launch-scope denominator. Separately, the tranche-5 running total at `:576` still reads "Sections swept: 21 of 37".
- **Evidence**: `docs/TRACEABILITY.md:57-58`, `:72`, `:99`, `:250-253`, `:576`, `:635`, `:759-773`; a per-section presence check across §5.0–§5.36
- **Evidence type**: docs
- **Verification limitations**: "Verdict-bearing" counted at top-level-section granularity, since ranged headings prevent a per-heading count; subsection-level verdicts (~197 subsections) were not audited.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — MEDIUM: "37 of 37 launch-scope sections" is an off-by-one against the file's own scope table (36 after excluding §5.17 "all of it"); the sweep itself is complete, so the defect is the arithmetic label on a gate-criterion claim. Also: stale tranche-5 running total at `:576`.)

#### TEST-08
- **Claim ID**: TEST-08
- **Domain**: audit-state
- **Intended state**: The "Open: none" line and a table still showing T-02 open were "both written in the same commit, `c44414f`".
- **Repository-observed state**: **The co-existence at `c44414f` is real; the "same commit" attribution is wrong.** `git show c44414f --stat` = 4 files, 183 insertions / 10 deletions (`docs/{DECISIONS,PROGRESS,ROADMAP,TRACEABILITY}.md`), dated **2026-07-30**, titled "Traceability tranche 6: 37 of 37 sections; criterion 1 turns on one sentence". In that commit's file state, `Open: none.` sits at L513 and the T-02 row reads `**Open.** Needs an explicit owner, not a fix.` at L518 — the contradiction was live in `c44414f`. **But neither line was written by it.** In the `c44414f` diff, the `Open: none.` line appears as an unchanged **context** line; `git log -S "Open: none" -- docs/TRACEABILITY.md` attributes its introduction to **`7430810`** (2026-07-30, "T-01 dispositioned: CloudTrail built, GuardDuty deferred; traceability tranche 2"), and `git log -S` on the T-02 row text attributes it to **`be6d22d`** (2026-07-30, "Traceability tranche 3 (minors/PII); T-02 filed"). `c44414f` touched no T-02 table row at all.
- **Evidence**: `git show c44414f --stat`; `git show c44414f -- docs/TRACEABILITY.md` (context-line prefix); `git show c44414f:docs/TRACEABILITY.md` L72/L513/L518; `git log -S "Open: none" -- docs/TRACEABILITY.md` → `2dd9e7e`, `7430810`; `git log -S "is not built and is owned only" -- docs/TRACEABILITY.md` → `be6d22d`; claim text at `docs/TRACEABILITY.md:641-645`
- **Evidence type**: git history
- **Verification limitations**: `-S` reports where a string's occurrence count changed; a same-commit add-and-remove could theoretically confuse it, though the context-line prefix independently confirms the line pre-existed `c44414f`. All git commands were read-only.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — LOW: the two contradicting lines were written in `7430810` and `be6d22d` and merely co-existed in `c44414f`; TRACEABILITY's self-cited near-miss names the wrong commit. This refutes the ledger's "both written in the same commit" as stated.)

#### TEST-09
- **Claim ID**: TEST-09
- **Domain**: traceability
- **Intended state**: T-01 closed with two opposite answers — CloudTrail module wired in staging (built half); GuardDuty absent (deferred half).
- **Repository-observed state**: Both halves confirmed at config level. CloudTrail wired — `environments/staging/main.tf:743-748` (see SEC-16). GuardDuty absent — no `aws_guardduty_*` resource anywhere in terraform, and the absence is deliberate and annotated at the wiring site: "GuardDuty, the other half of T-01, is deliberately NOT here - deferred with a written reason in D-125, on the same always-on-cost argument that deferred WAF in D-087" (`:740-742`), echoed at `modules/cloudtrail/main.tf:10`.
- **Evidence**: as cited above
- **Evidence type**: terraform config + negative grep
- **Verification limitations**: Configuration only; the live-verified half of T-01 (CloudTrail `IsLogging`) is Phase 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — config half fully confirmed for both the built and the deferred answer)

#### TEST-10
- **Claim ID**: TEST-10
- **Domain**: traceability
- **Intended state**: T-02 dispositioned (D-129) and split — the §6.1 legal track enumerates the eleven disclosures as a written deliverable, S45 builds the notice, the order is load-bearing (the disclosure list gates the build), and the item is explicitly still not built.
- **Repository-observed state**: **The disposition text is present as claimed.** `docs/TRACEABILITY.md:650` (T-02 row): "**Dispositioned 2026-07-30 (D-129): S45 builds it; the §6.1 track enumerates the eleven disclosures first.** Scheduled, not shipped — see below." The split and the load-bearing ordering are spelled out at `:655-662`, and `:664-665` "**Still not built**, and the disposition does not pretend otherwise." **Notice component: still absent** — same evidence as SEC-20 (no notice/disclosure component or first-visit gate anywhere in `apps/learning-web/src`; only route-keyed comments anticipating one). **§6.1 track: started, and the gating deliverable produced** — `docs/FIRST_VISIT_NOTICE.md` (2026-08-15, `da2549f`) enumerates all eleven as copy for S45 to transcribe, and `docs/ROADMAP.md:2148-2157` now carries the enumeration in the §6.1 parallel-track block. **The order held**: the list landed before any build, which is precisely what the claim says must happen. **Two statements inside TRACEABILITY's T-02 block are now false of the repo**, though both sit under the explicit preservation marker at `:668` "*(The finding as filed, kept because the reasoning is the record:)*": `:685-690` "The §6.1 legal & policy parallel track, which 'gates the pilot' and has **not started**", and `:680` "**None of the eleven is enumerated as a deliverable anywhere in ROADMAP.md.**" ROADMAP now enumerates them and a dedicated file writes them out. TRACEABILITY contains **no reference to `docs/FIRST_VISIT_NOTICE.md`** — a grep for `FIRST_VISIT_NOTICE` across `docs/` hits only `PROGRESS.md:978` and `:2246` — so the traceability document does not cite the artifact that discharged its own prerequisite.
- **Evidence**: `docs/TRACEABILITY.md:650,652-698` (esp. `:655-665,668,680,685-690`); `docs/FIRST_VISIT_NOTICE.md:1-14,203-222,233-237`; `docs/ROADMAP.md:1408,1502-1504,2148-2157`; `docs/PROGRESS.md:978-982,2246`; `apps/learning-web/src/` inventory. Commands: `grep -rn "FIRST_VISIT_NOTICE" docs/ --include="*.md"`, `sed -n '645,700p' docs/TRACEABILITY.md`, `ls -R apps/learning-web/src`
- **Evidence type**: docs + negative grep (component absence)
- **Verification limitations**: Absence scoped to `apps/learning-web/src`; counsel review and any pilot/legal sign-off are off-repo → 3B; nothing executed.
- **Classification**: CONFIRMED_IN_REPOSITORY (the plan claim holds: notice unbuilt, ordering respected, disclosure list produced first. Drift LOW: `TRACEABILITY:680` and `:685-690` are now untrue of the repo — softened by the `:668` preservation marker, but the block never adds a "since superseded" pointer to `FIRST_VISIT_NOTICE.md`. The only decision required is the shared eight-vs-eleven question carried by WORK-33.)

#### TEST-11
- **Claim ID**: TEST-11
- **Domain**: verification-method
- **Intended state**: Traced-to-deleted-code (D-226 rewrote the §5.8.3–.5 rows): the authored route exists and is the traced implementation; the shape route was deleted; the named rejection tests exist.
- **Repository-observed state**: Confirmed with one naming discrepancy. Shape route absent: no `test_ai_pipeline.py` anywhere; no `validation.py` in `packages/curriculum/src/intellichoice_curriculum/` (only `authored_validation.py`); `generate_candidate` survives only in two prose comments (`pipeline_cli.py:8`, `packages/db/src/intellichoice_db/models/questions.py:120`), and `pipeline_cli.py:507` states "One candidate function, since D-226 removed the shape route." Authored route exists: `ai_pipeline.py` implements equation design (`:1247`) → generator (`:1329`) → two solvers reusing `QUESTION_GENERATION`/`QUESTION_REVIEW` (`:1911`, `:1923`) → judge (`:1970`) → `validate_authored_item` (`:1810`) → dedup (`:1821-1840`). Named rejection tests, all in `packages/curriculum/tests/test_authored_pipeline.py`: `:604` ✓, `:632` ✓, `:675` ✓, `:725` ✓, `:1306` ✓, `:872` ✓. **`test_judge_flags_reject_and_borderline_score_sets_high_priority` does not exist under that name** — the file has `test_judge_flags_reject_and_a_borderline_score_no_longer_sets_high_priority` (`:774`), a rename that inverts the second clause's meaning (D-249 removed the borderline→high-priority routing).
- **Evidence**: `docs/TRACEABILITY.md:280-315`, `:313`; `packages/curriculum/tests/test_authored_pipeline.py:604, 632, 675, 725, 774, 872, 1306`; `pipeline_cli.py:507`; directory listing of `packages/curriculum/src/intellichoice_curriculum/`
- **Evidence type**: test-source (name enumeration) + negative grep
- **Verification limitations**: "Exist and pass" — only existence is verified. Test collectability (imports resolve) was not checked either.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — for the substance: authored route traced, shape route deleted, six of seven named tests exist. LOW drift: `TRACEABILITY:313` cites a test name that was renamed to assert the OPPOSITE routing (D-249) — an unresolvable citation inside the traceability register itself.)

#### TEST-12
- **Claim ID**: TEST-12
- **Domain**: verification-method
- **Intended state**: `test_editing_an_item_already_in_the_database_propagates` exists and asserts both halves — the edit lands in the DB, and an edit that breaks the item fails the load.
- **Repository-observed state**: Confirmed. The test is at `packages/curriculum/tests/test_authored_bank.py:274-322`. Half one: after re-loading an edited item under the same id it asserts `row.difficulty_label == 4, "the file's tier never reached the database"`, `row.skill_id == "linear_two_step"`, and `summary.templates_updated == 1`. Half two, under the comment "an edit that breaks the item must fail the load rather than be applied, which is the half the skip made unreachable": `with pytest.raises(CurriculumLoadError)` around a load of an item whose `answer_expression` no longer matches its options. The fix is present in the loader: `loader.py:161` calls `validate_authored_item`, and `:246-263` reads the existing row, computes `_drifted(...)` over template and variant fields, and updates in place rather than skipping by id (`:255` increments `templates_skipped_existing` only when nothing drifted). `LoadSummary` gained `templates_updated` (`:62`).
- **Evidence**: `packages/curriculum/tests/test_authored_bank.py:274-322`; `packages/curriculum/src/intellichoice_curriculum/loader.py:58-62, 154-161, 186-199, 209, 235-263, 322-349`
- **Evidence type**: test-source + code
- **Verification limitations**: Existence and assertion content verified; pass/fail not. The test requires a live DB session (`_rollback_session`), so it may be skipped in environments without Postgres — whether it is gated by a fixture skip was not determined.
- **Classification**: CONFIRMED_IN_REPOSITORY (carries a TEST_EXISTS_NOT_EXECUTED limitation as written)

#### TEST-13
- **Claim ID**: TEST-13
- **Domain**: verification-method
- **Intended state**: The floor-reading lesson (traced ≠ enforced) — both floors now exist as measured constants with band-asserting tests.
- **Repository-observed state**: Both constants present with their measurement written into the source. `MIN_RERANK_RELEVANCE_SCORE = 0.35` at `packages/knowledge/src/intellichoice_knowledge/retrieval.py:304`, preceded by the sweep table and the instruction "Do not raise this without re-running the sweep"; enforced at `:387-390` (`score > min_relevance_score`) and threaded through config (`apps/chat-api/src/chat_api/config.py:96`) and `nodes.py:258`. `MIN_CITATION_QUOTE_CHARS = 20` at `apps/chat-api/src/chat_api/services/qa.py:152`, enforced on the *normalized* quote at `:182-184` before the containment check, and stated to the model in the synthesis prompt (`:255`). Band-asserting tests exist as source: `packages/knowledge/tests/test_retrieval.py:375-378` (`assert 0.30 <= MIN_RERANK_RELEVANCE_SCORE < 0.60`) and `apps/chat-api/tests/test_qa_service.py:369-395` (`test_the_quote_floor_is_measured_at_its_own_boundary`, one char either side of the constant), plus `test_the_quote_floor_excludes_only_heading_chunks` referenced at `qa.py:150`.
- **Evidence**: as cited above
- **Evidence type**: code + test-source
- **Verification limitations**: Tests not run; the "traced means the floor was read" claim is a method statement, verifiable only by the constants' presence and their guards.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### TEST-14
- **Claim ID**: TEST-14
- **Domain**: testing
- **Intended state**: The named test exists and pins the deliberately-unapplied floor on the reranker-degraded path; the degraded path is loud.
- **Repository-observed state**: `packages/knowledge/tests/test_retrieval.py:381` defines `test_the_floor_does_not_apply_when_the_reranker_is_unavailable`; it injects `StructuredOutputError("reranker down", cost_cents=0.1)` and asserts `[c.chunk_id for c in result.chunks] == ["a", "b"]` — both unscored candidates survive. Its docstring restates D-172 §3's reasoning in substance. The loudness half is separately pinned at `:271` (`degraded = [r for r in caplog.records if r.message == "retrieval_rerank_degraded"]`). The implementation side matches (see REQ-15).
- **Evidence**: `packages/knowledge/tests/test_retrieval.py:265-275`, `:381-405`; `packages/knowledge/src/intellichoice_knowledge/retrieval.py:359-375`
- **Evidence type**: test-source
- **Verification limitations**: "And passes" cannot be confirmed — tests were not executed.
- **Classification**: TEST_EXISTS_NOT_EXECUTED (adjudicated centrally — existence and content confirmed)

#### TEST-15
- **Claim ID**: TEST-15
- **Domain**: audit-state
- **Intended state**: The AUDIT_FINDINGS register shows 0 open findings, derived rather than read.
- **Repository-observed state**: **The anchored awk returns 0.** Executed verbatim from ROADMAP against the current `docs/AUDIT_FINDINGS.md`: zero ids emitted, `wc -l` = **0**. The register's self-report and the derived figure agree.
- **Evidence**: awk from `docs/ROADMAP.md:768-771` run against `docs/AUDIT_FINDINGS.md` → 0 rows; register self-report at `docs/AUDIT_FINDINGS.md:159-169`
- **Evidence type**: docs (instrument executed read-only against in-repo files)
- **Verification limitations**: §9 filed this as a group-(c) re-measurement, but the instrument is repo-local, so it was answerable in 3A. This is the Phase-0B register only; `AUDIT_LIVE_2026_08_17.md` is a separate namespace with its own open list and is not covered by this count.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### TEST-16
- **Claim ID**: TEST-16
- **Domain**: verification-method
- **Intended state**: The open count must be derived by ROADMAP's anchored awk, never read from a sentence.
- **Repository-observed state**: **Actual output number: 0.** The recipe at `docs/ROADMAP.md:768-771` is intact and executable as written (no shell adaptation needed), and its output matches ROADMAP's own recorded expectation ("That returns **0** as of 2026-08-05 (D-183)") and AUDIT_FINDINGS' arithmetic line. ROADMAP's four recorded prior wrong values (6 → 5 → 3 → 1 → 0) and the "wrong twice before" argument are both present at `:709-712` and `:783-784`.
- **Evidence**: `docs/ROADMAP.md:706-712`, `:761-773`, `:783-784`; `docs/AUDIT_FINDINGS.md:166`; awk output = 0
- **Evidence type**: docs (instrument executed read-only)
- **Verification limitations**: None — this is the designated tiebreaker and it ran clean. As with TEST-15, §9 filed it as group (c) but the instrument is repo-local.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### TEST-17
- **Claim ID**: TEST-17
- **Domain**: audit-state
- **Intended state**: 27 findings had a detail section and no Index row; the "one row per finding" invariant holds after D-174's backfill (0 exceptions).
- **Repository-observed state**: **Invariant holds in the asserted direction — 0 exceptions.** Scripted diff: 94 `### AUD-` section headings → **93 unique ids** (the one duplicate is `AUD-C-16`, the known-benign two-section finding D-178 checked); Index rows across both halves → **100 unique ids**. `comm` of sections-minus-rows = **empty**: every section has a row. The inverse direction shows **7 row ids with no `### AUD-` detail section** — `AUD-F-05` (folded into the combined heading `### AUD-F-04 / AUD-F-05`) plus `AUD-F-16, F-17, F-18, F-19, F-20, F-38` (rows only). The file itself flags this direction at `:105`.
- **Evidence**: `docs/AUDIT_FINDINGS.md:103-123`, `:131-150`, `:179-180`, `:105`, `:89-94`; `docs/ROADMAP.md:734-747` (the invariant); scripted section/row id diff
- **Evidence type**: docs (content-state derivation)
- **Verification limitations**: Id extraction keyed on `^### AUD-<L>-<N>` and pipe-field-2; a heading using a different format would be missed (the `AUD-F-04 / AUD-F-05` case shows this is a real pattern).
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — 0 exceptions in the asserted direction. LOW drift: the reverse invariant is unheld — 6 findings have Index rows but no detail section.)

#### TEST-18
- **Claim ID**: TEST-18
- **Domain**: verification-method
- **Intended state**: The four recorded failure modes of the counting instrument — the four extra-pipe rows still keep their status in field 5.
- **Repository-observed state**: **Confirmed — all four intact.** Field-count check on the named rows: `AUD-C-14`, `AUD-C-15`, `AUD-L-16`, `AUD-F-16` each have **NF=8** (against the 7-field norm), and each `$5` begins with `✅ **fixed...` — a real status string, correctly positioned, and correctly not matching `^Open`. The stray pipe sits in the description cell after field 5 in every case, exactly as D-178 recorded. The benign `### AUD-C-16` duplicate is also confirmed as the sole duplicate section id.
- **Evidence**: `docs/AUDIT_FINDINGS.md:42`, `:59`, `:60`, `:90`; `docs/ROADMAP.md:734-765`, `:749-753`, `:786-790`; awk NF/field-5 check
- **Evidence type**: docs (content-state derivation)
- **Verification limitations**: None material.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### TEST-20
- **Claim ID**: TEST-20
- **Domain**: audit-state
- **Intended state**: The AUD-L-17 → AUD-L-19 renumber was applied per reference; ranges and the P3 narrative deliberately left; pre-2026-08-04 docs still cite the P2 as `AUD-L-17`.
- **Repository-observed state**: **41 surviving `AUD-L-17` citations corpus-wide (36 excluding CLAIM_LEDGER's own 5), classified:** AUDIT_LIVE namespace (1): `docs/AUDIT_LIVE_2026_08_17.md:43` — "Child chooser has no sign-out or exit", P3, a wholly separate register the file's own disambiguation heuristic cannot reach. Range (5): `PROGRESS.md:5378`, `:10039`, `:13016`; `AUDIT_FINDINGS.md:198`; `DECISIONS.md:3971`, `:11203` — all the S36 span `AUD-L-10..AUD-L-17`, correctly ending at the P3, deliberately left. P3-meaning (12): `AUDIT_FINDINGS.md:43`, `:73`, `:1171`, `:3203`, `:3209`, `:3218`, `:3219`, `:3221`; `PROGRESS.md:9949`, `:9951`; `DECISIONS.md:4048`, `:4263-4267`. P2-meaning (2, both explicitly historical): `AUDIT_FINDINGS.md:35` (the renumber note) and `DECISIONS.md:11207` — **no live, unqualified P2-meaning citation survives.** Renumber-meta/disambiguation (11) and reconciliation-corpus meta (5) account for the rest.
- **Evidence**: 41-hit `grep -rn "AUD-L-17" --include="*.md"` over the repo; `docs/AUDIT_FINDINGS.md:182-200`, `:35`, `:43`; `docs/ROADMAP.md:744-745`
- **Evidence type**: docs (content-state derivation)
- **Verification limitations**: Classification of narrative passages is a reading of intent from surrounding text, not a mechanical property. The ledger's "33 places across five documents" is a 2026-08-04 snapshot, now 36 non-ledger hits across seven files as the reconciliation corpus added its own.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — renumber applied per reference; snapshot count now 36 non-ledger hits. MEDIUM drift: a bare `AUD-L-17` resolves to two live findings in two registers and the documented disambiguation heuristic does not work across documents.)

#### TEST-22
- **Claim ID**: TEST-22
- **Domain**: testing
- **Intended state**: The six named specs/tests created by D-383's closures of the 2026-08-17 audit's three blind spots exist.
- **Repository-observed state**: All six exist. `e2e/tests/learning/journey-terminal.spec.ts` (473 lines, 1 test) — sign-in → pre-exam → study → post-exam → results screen; states no walk had ever reached the results screen. `e2e/tests/learning/attendance-email-approved.spec.ts` (117 lines, 1 test) — approving the branch-manager email confirms, closes, and leaves the gate closed; its docstring records the narrowing TEST-23 describes. `e2e/tests/chat/escalation-approved.spec.ts` (98 lines, 1 test) — "Approve & send" against the real backend. `e2e/tests/learning/error-vocabulary.spec.ts` (232 lines, 1 test) — every sentence learning-web's `errors.ts` can produce rendered at least once. `e2e/tests/chat/error-states.spec.ts` (455 lines, 13 tests) — 401/403/409×3/429×N/504/503/over-length in a real browser. `apps/learning-api/tests/test_error_detail_contract.py` (4 tests) and `apps/chat-api/tests/test_error_detail_contract.py` (2 tests) — pin the `errors.ts` substrings to details the APIs actually send; both docstrings name D-378.
- **Evidence**: the seven file paths above, with test counts from `grep -cE '^\s*(test|it)\('` / `def test`
- **Evidence type**: test-source
- **Verification limitations**: Never executed; existence and stated intent only — pass/fail status unknown.
- **Classification**: TEST_EXISTS_NOT_EXECUTED (adjudicated centrally — all six closure artifacts exist; content matches)

#### TEST-23
- **Claim ID**: TEST-23
- **Domain**: audit-state
- **Intended state**: API-level approvals had happened while UI approvals had not — the two named pytest tests exist and assert the send, the recipient, and an `InterruptApproval` row.
- **Repository-observed state**: Both exist and assert all three, on both apps. The learning-api test additionally asserts nothing was sent before approval. `test_admin_escalation` is a module, not a single function — it contains `test_admin_escalation_pauses_then_sends_only_after_approval` and `test_admin_escalation_declined_sends_nothing`.
- **Evidence**: `apps/learning-api/tests/test_learning_flow.py:2023` `def test_attendance_ask_branch_manager_end_to_end()` — `assert pending["interrupt_type"] == "email_approval"`, `assert preview["recipient"] == "manager.main@example.test"`, `assert app.state.email_transport.sent == []` (pre-approval), then `assert len(app.state.email_transport.sent) == 1`, `assert app.state.email_transport.sent[-1].recipient == "manager.main@example.test"`, `approvals = _interrupt_approvals(session_id)` / `assert len(approvals) == 1` / `assert approvals[0].decision == "approved"` / `assert approvals[0].interrupt_type == "email_approval"`; `apps/chat-api/tests/test_admin_escalation.py:185-217` with the declined arm at `:221-240`
- **Evidence type**: test-source
- **Verification limitations**: Not executed — the claim that these "had been approved at the API level" rests on these passing. Both use fake/recording transports, so they assert the send *decision*, not a real send. The corrected-vs-uncorrected wording collision in `AUDIT_LIVE_2026_08_17.md` was not re-read. Separately, a browser-level walk now exists (`e2e/tests/learning/attendance-email-approved.spec.ts`), bearing on the "UI approvals had not happened" half — existence only.
- **Classification**: TEST_EXISTS_NOT_EXECUTED (adjudicated centrally — both tests exist asserting send, recipient and approval row)

#### TEST-25
- **Claim ID**: TEST-25
- **Domain**: open-work
- **Intended state**: The three "still un-walked" items are in fact closed by specs outside the AUDIT_LIVE file (D-391 exam timer, D-399 `.ics` DOM contract, D-398 tutor-chat browser leg), plus the same-family D-387/D-388/D-392 specs.
- **Repository-observed state**: All six specs exist. `e2e/tests/learning/exam-expiry.spec.ts` (143 lines) — docstring opens "D-391: the exam timer runs out, and the student is not trapped"; parameterised on `remaining=`. `e2e/tests/chat/ics-download-dom-contract.spec.ts` (149 lines) — "D-399 ... hold D-352 by watching the calls, not the browser"; asserts the anchor appended before click and revoke on a later tick. `e2e/tests/learning/pii-typed-into-tutor-chat.spec.ts` (190 lines, 2 tests) — "D-398: the leg V7 deferred". `e2e/tests/chat/calendar-branches.spec.ts` (D-392, 2 tests), `e2e/tests/chat/pii-typed-by-a-visitor.spec.ts` (D-387, 2 tests), `e2e/tests/security/deployed-authorization.spec.ts` (D-388, 6 tests — matching the "6/6" in the claim).
- **Evidence**: the six paths above; each file's opening docstring names its decision ID
- **Evidence type**: test-source
- **Verification limitations**: Not executed. `docs/AUDIT_LIVE_2026_08_17.md:105-142` was not re-read to re-confirm the file was never updated; the ledger already records that.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — for the closure specs; the ledger's PARTLY-SUPERSEDED reading is confirmed, and AUDIT_LIVE's stale still-open list is already registered, so no new entry)

#### TEST-26
- **Claim ID**: TEST-26
- **Domain**: testing
- **Intended state**: Error-vocabulary closure counted against a programmatic enumeration — learning-web `errors.ts` = 10 rules, chat-web = 8 (18 total).
- **Repository-observed state**: Counts match. `apps/learning-web/src/api/errors.ts:46-109` `RULES` has exactly 10 entries — 409 already-answered, 409 time-limit, 409 not-an-item, 409 not-accepting-answers, 409 select-a-student, 409 catch-all, 401, 403, 404, 429 (the removed `{status:400, detail:["attendance"]}` rule survives only as a comment block at lines 96-107 explaining why it could never fire). `apps/chat-web/src/api/errors.ts` `RULES` (lines 50-96) has exactly 8 entries by `status:` key — 422, 409, 409, 409 catch-all, 401, 403, 504, 429. The claim's "learning-web's 401 excluded with a reason" is corroborated by `errors.ts:115-120`, where `isSignedOut` is exported for the D-375 sign-out path.
- **Evidence**: `apps/learning-web/src/api/errors.ts:46-109`; `apps/chat-web/src/api/errors.ts:50-96` (enumerated by `grep -n "status:"`, comment-only occurrences excluded by reading each hit)
- **Evidence type**: code (source enumeration)
- **Verification limitations**: Rule count is a static property; "18 of 18 rendered" is a run-time property unverifiable without executing the suite.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — 10 and 8 confirmed. LOW drift: `e2e/tests/learning/error-vocabulary.spec.ts:5-7` still describes learning-web's table as "twelve rules, five of them different 409s".)

#### TEST-27
- **Claim ID**: TEST-27
- **Domain**: testing
- **Intended state**: `capture.ts` attaches console+network capture to every page and enforces zero console errors, zero 5xx and zero blank/stuck states at teardown, narrowable only via `audit.allow({...})`, with one JSONL line per test appended to `artifacts/journeys.jsonl`.
- **Repository-observed state**: `e2e/fixtures/capture.ts` (270 lines). `attach()` registers `console`, `pageerror`, `requestfailed` and `response` listeners on every page. `assertClean()` asserts four things: `pageErrors === []`, `consoleErrors === []`, `serverErrors === []` (skippable via `allowances.serverErrors`), `failedRequests === []` (skippable). Narrowing is via `AuditLog.allow()`; `ScopedConsoleError` requires a URL match, and the docstring records D-355 (a bare `"Failed to load resource"` string forgave every failing request in a walk). `clientErrors` (4xx) is explicitly documented as "reported, not enforced — no assertion reads it". `persist()` appends one `JSON.stringify(summary)` line to `../artifacts/journeys.jsonl` via `appendFileSync` and writes a per-test `audit.json` attachment. The fixture teardown calls `persist` then `if (testInfo.status === "passed") log.assertClean()`. **"Zero blank/stuck states" is NOT a distinct teardown assertion** in `assertClean()`: blank/stuck is carried by (a) the `pageerror` listener, whose comment ties it to the blank-screen findings, and (b) per-spec helpers `expectNotBlank`/`expectNotStuck` imported from `e2e/fixtures/session.ts` (e.g. `journey-student.spec.ts:13`) — asserted in-test, not over the whole run at teardown. Second nuance: `assertClean()` runs only when `testInfo.status === "passed"` (deliberate, per its comment), so a failing test's criterion-3 evidence is reported but not enforced.
- **Evidence**: `e2e/fixtures/capture.ts` — `assertClean()` (~136-159), `persist()` (~236-260), `test.extend` block (~262-270), `Allowances`/`ScopedConsoleError` interfaces (~39-80); `e2e/fixtures/session.ts`; `e2e/tests/learning/journey-student.spec.ts:13`
- **Evidence type**: test-source
- **Verification limitations**: Not executed; whether `journeys.jsonl` is in fact written per run is inferred from the code path.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally, with DOCUMENTATION_DRIFT MEDIUM — "zero blank/stuck states" is not a teardown assertion (per-spec helpers only), and `assertClean` runs only when the test otherwise passed, so `e2e/README.md` and the ledger claim overstate teardown enforcement)

### 3.6 INT family — 15 claims

#### INT-06
- **Claim ID**: INT-06
- **Domain**: integration
- **Intended state**: The §3.1 auth decision gate reads as live against frozen reality — SUPERSEDED as to timing/urgency by D-152/D-153.
- **Repository-observed state**: **Confirmed — `grep -c "D-152\|D-153" docs/INTEGRATION_PLAN.md` = 0.** Zero mentions of either decision anywhere in the file. The document's front matter is a 2026-07-24 "Rewritten ... under a hardened scope constraint" block about production immutability; **there is no freeze banner and no pre-freeze-artifact disclaimer** at the top. The §3.1 gate text and §5's S42 row both still read as live and forward-looking.
- **Evidence**: `docs/INTEGRATION_PLAN.md:1-15` (front matter, no freeze banner); zero-hit `D-15[23]` grep; gate text at `:281-288`; contrast `docs/ROADMAP.md:1438-1445`, which *does* carry the ⛔ banner
- **Evidence type**: docs (negative grep)
- **Verification limitations**: Lookup only, per assignment.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the absence is verified exactly as the ledger states. Drift **HIGH**: INTEGRATION_PLAN.md carries no trace of the freeze; a reader arriving from `ROADMAP.md:1438` gets the banner, a reader arriving at the file directly does not.)

#### INT-07
- **Claim ID**: INT-07
- **Domain**: integration
- **Intended state**: Reconcile INTEGRATION_PLAN §5's session table and dependency spine against actual session history.
- **Repository-observed state**: Per-row status against ROADMAP/PROGRESS (table at `:455-476`): S35 **done**; S36 (AUD-L) **done**; S37 (AUD-C) **done**; S38 (AUD-X) **done**; S39 (AUD-F) **done**; S40–S41 **done**, backlog empty per D-183 (2026-08-05); Gate **closed 2026-08-01 (D-148)**, criterion 6 closed early by user decision, criteria 2 qualified by R8/R9; S42 **partial** — source half done 2026-08-01 (D-151), measurement half **frozen** (D-152), §3.1 auth option and I11 rung recommended NOT decided; S43–S47 **frozen** (D-152), with S45 independently blocked on the unstarted §6.1 legal track; S48–S51 **not started** (S50 additionally missing GuardDuty from its scope, see SEC-17). The table's own "indicative beyond S41" caveat is present at `:451-452`, but nothing in §5 records the freeze, and the dependency spine at `:479-482` still reads as a live sequence. Post-gate work in fact ran as an unnumbered W-series (W1–W27, D-393→D-423, 2026-08-17/18) that §5 does not model at all.
- **Evidence**: `docs/INTEGRATION_PLAN.md:448-482`; `docs/ROADMAP.md:1438-1521` (freeze banner + S42–S51), `:2806-3304` (W1–W27 session records); `docs/DECISIONS.md:8635` (D-148 gate closure); `docs/PROGRESS.md:1238`
- **Evidence type**: docs
- **Verification limitations**: S48–S51 "not started" is inferred from the absence of session records, not from an explicit statement.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — **HIGH**: §5's table is accurate for S35–S41 and the Gate, wrong-as-current for S42, silently wrong for frozen S43–S47, and has no representation of the 27 W-sessions that actually ran. One register entry covers INT-06 and INT-07, plus INT-26/INT-28's sibling files.)

#### INT-12
- **Claim ID**: INT-12
- **Domain**: integration
- **Intended state**: Our-side allowlist constraint does not relax if the org fixes role validation; the allowlist is designed into S43/S44 work when written.
- **Repository-observed state**: Same finding as SEC-34. The S43 block carries the constraint with all three grounds and the operative instruction ("Map Student/Parent from production; gate `Tutor`/`Manager` behind an allowlist the new stack controls"), plus "fail-closed role mapping" in the S43 header and the I12 deploy-time schema smoke probe. Restated identically in three other places. **No allowlist mechanism is specified** (no storage, admin path, or seeding), and S43 is frozen so nothing is "written" yet.
- **Evidence**: `docs/ROADMAP.md:1465-1491` (constraint at `:1482-1489`); `docs/DECISIONS.md:9115-9120`, `:9162-9170`; `docs/S42_DISCOVERY.md:238-241`; `docs/S42_OPEN_QUESTIONS.md:33-37`
- **Evidence type**: docs
- **Verification limitations**: As SEC-34 — "design" judged by the presence of a stated mechanism in the S43-scoped docs; no source inspection (S43 code does not exist).
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — the constraint is consistently and prominently placed in the session that will implement it; no drift)

#### INT-13
- **Claim ID**: INT-13
- **Domain**: org-comms
- **Intended state**: The §6.2 disposition moved from "accepted" to "to be fixed by the org", so §6.2 joins §6.1/§6.3/§6.4 on the list the user will send; the send is not yet confirmed.
- **Repository-observed state**: **No sent record.** A corpus grep across PROGRESS/DECISIONS/ROADMAP for send/notification language in English and Korean (`통지`, `발송`, `notify the org`, `notified`, `sent to the org`, `전달`) returns **zero** confirmations. The affirmative evidence runs the other way: `S42_SECURITY_REPORT.md:12` still reads "**Send:** §6.1 ..., §6.2 ..., §6.3 ..., §6.4", the report header carries only a Drafted date, and PROGRESS's live pointer still lists sending as the user's outstanding step.
- **Evidence**: `docs/S42_SECURITY_REPORT.md:1-13`; `docs/PROGRESS.md:7726`, `:13703`; `docs/S42_OPEN_QUESTIONS.md:22`, `:31-32`, `:39-40`; `docs/DECISIONS.md:9105-9109`, `:9156-9160`; zero-hit send/notification grep
- **Evidence type**: docs (negative grep)
- **Verification limitations**: Negative evidence; an out-of-band send would be invisible here.
- **Classification**: CONFIRMED_IN_REPOSITORY (the documentation correctly represents the open action as open in three places; the real-world consequence is carried by the SEC-32 unsent-report drift entry covering SEC-32/INT-13/INT-25)

#### INT-15
- **Claim ID**: INT-15
- **Domain**: integration
- **Intended state**: `attendanceClaimed` is a fail-open trap; no adapter or derivation code reads it — zero code reads expected.
- **Repository-observed state**: Zero code reads. A repo-wide grep (excluding node_modules/.git/.venv) returns 16 hits, all in Markdown: `docs/INTEGRATION_PLAN.md`, `docs/S42_DISCOVERY.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, `docs/reconciliation/*`. No `.py`, `.ts`, `.tsx`, `.sql`, or `.tf` hit.
- **Evidence**: `docs/INTEGRATION_PLAN.md:610` "**`attendanceClaimed` must never gate an exam.**"; `docs/DECISIONS.md:3916`, `:3924` "**Only `attended === true` may mean present.**"; `docs/S42_DISCOVERY.md:55`; zero code hits
- **Evidence type**: negative grep
- **Verification limitations**: The requirement binds S43 code that does not exist yet, so this is compliance-by-absence, not compliance-by-construction. The PII-projection half of the claim (`firstName`/`lastName`/`children` projected to external ids at the adapter boundary) is equally untestable — no adapter exists to inspect.
- **Classification**: DEFERRED_BY_D152 (adjudicated centrally — compliance-by-absence confirmed; nothing violates yet)

#### INT-19
- **Claim ID**: INT-19
- **Domain**: integration
- **Intended state**: The consent ledger (I9) — no consent row → no token — with consent *text* coming from the §6.1 legal parallel track, "a true pilot blocker".
- **Repository-observed state**: **The §6.1 track has not started, and it now gates more than the pilot.** ROADMAP's "Parallel track (any time, non-coding) — Phase 0 legal & policy docs (§6.1)" carries no start or progress marker; PROGRESS states that "the §6.1 track gates the pilot, **has not started**, and already carries D-114 §4's obligation." D-129 additionally made it gate a *coding* session: "**Now also gating a coding session (D-129, T-02): enumerate §5.1.2's eleven first-visit disclosures** ... as a written deliverable **S45 transcribes rather than drafts**." ROADMAP confirms "§6.1 legal docs gate the pilot" in the dependency spine. Refined by W10: the §6.1 track is no longer wholly unstarted (the T-02 disclosure-enumeration deliverable shipped 2026-08-15 as `docs/FIRST_VISIT_NOTICE.md`); the Privacy Notice/consent text, counsel review, an owner, and a schedule remain missing.
- **Evidence**: `docs/ROADMAP.md:2148-2160` (track definition, no status), `:1502`, `:1504`, `:1526`; `docs/PROGRESS.md:8447`; `docs/INTEGRATION_PLAN.md:357-363`, `:437`, `:467`
- **Evidence type**: docs
- **Verification limitations**: "Not started" rests on PROGRESS's assertion plus the absence of any deliverable; `FIRST_VISIT_NOTICE.md` is partial coverage of the disclosure-enumeration sub-deliverable but is explicitly "not the Privacy Notice, and not a substitute for counsel review".
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — drift recorded as **HIGH-adjacent MEDIUM**: the §6.1 legal track gates the pilot AND frozen S45 AND, per D-129, a coding deliverable, with no owner, schedule, or status anywhere)

#### INT-22
- **Claim ID**: INT-22
- **Domain**: integration
- **Intended state**: The §2.6 gate closed 2026-08-01 (historical); a criterion-6 early-close rationale exists; R8/R9 expiry conditions are still tracked.
- **Repository-observed state**: **Criterion-6 rationale: present and unusually explicit.** D-148's heading is "criterion 6 closed early by user decision, on manufactured-but-real evidence: a Scheduler-initiated firing today instead of two calendar Sundays", and §1 records the user's words ("just bypass that blocker for once"), the mechanism (a one-off EventBridge schedule cloning the real target), and the evidence (`startedBy: chronos-schedule/...`, exit 0, 24.73¢ spent, real weekly schedule verified untouched) — plus the framing "so the bypass is a documented reading change, not an undocumented shortcut". **R8/R9 expiry tracking: nothing actively monitors them.** The expiry conditions exist in exactly one authoritative place (`INTEGRATION_PLAN.md:503-507`, `:535`, `:551-565`) with narrative echoes in PROGRESS/ROADMAP; the copies in `ARCHITECTURE.md` carry the risks **without** the expiry conditions. No dashboard, alarm, checklist, or open-item register tracks either trigger. R8's named closure is S43/S46 (frozen); R9's is the commit-ordering fix, recorded untouched in `AUDIT_FINDINGS.md:71`.
- **Evidence**: `docs/DECISIONS.md:8635-8660` (D-148 §1); `docs/INTEGRATION_PLAN.md:192-214`, `:500-517`, `:535`, `:551-565`; `docs/ARCHITECTURE.md:605-609` (R9 without expiry); `docs/AUDIT_FINDINGS.md:71`; `docs/PROGRESS.md:8523-8524`, `:14176-14177`; `docs/ROADMAP.md:1344-1349`
- **Evidence type**: docs
- **Verification limitations**: "Actively monitored" assessed from docs only. The terraform half was checked independently under SEC-10 and confirms the negative: no alarm references `learning_checkpoint_repairs_total`.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — both halves of the ledger's characterization hold: the closure is real, qualified by carve-outs nothing watches. Covered by the one HIGH register entry spanning SEC-33, INT-22, INT-33.)

#### INT-23
- **Claim ID**: INT-23
- **Domain**: production-fact
- **Intended state**: `signups.attended = null` is routine, so UNKNOWN → blocked is a routine path; fail-closed is already correct, and what needs attention is the blocked screen's wording, the student's next step, how a late marking recovers, and an e2e fixture exercising the UNKNOWN path in a browser.
- **Repository-observed state**: All four landed. (1) Wording: a distinct `UNKNOWN_MESSAGE` reframes the block as not-yet-recorded. (2) Next step: the ask-branch-manager path with an approval dialog. (3) Recovery: the message directs the student to retry once updated, and approving the email explicitly does not establish attendance. (4) e2e: a dedicated unmarked-attendance fixture drives the UNKNOWN path in a real browser and asserts the distinct wording.
- **Evidence**: `attendance.py:42-50` (`UNKNOWN_MESSAGE`) and `:120`; `:61-64` `EMAIL_SENT_MESSAGE` "This week's practice stays paused until then."; `e2e/config.ts:137` `studentUnknownAttendance: { role: "student", sub: "student-ext-3" }` with `:134-135`; `e2e/tests/learning/journey-attendance.spec.ts:78-113` — `expect(gateMessage, "the unknown-attendance block should read as not-yet-marked, not as a recorded absence").toContain("not been marked yet"); expect(gateMessage).not.toContain("did not receive");` plus `:115-122`; second fixture at `e2e/config.ts:171-176`, whose spec's `:104-110` asserts "approving the email does not establish attendance ... (SPEC §5.6.4 'Session remains blocked')"; `apps/learning-web/src/lib/attendanceLabels.ts:22` with D-407 rationale at `:1-14`
- **Evidence type**: code + test-source
- **Verification limitations**: e2e specs not executed, and `journey-attendance.spec.ts:99-102` contains a self-skip when an earlier run already resolved the gate, so a green run would not guarantee the wording assertion executed. The dev fake's understatement of UNKNOWN frequency (`S42_DISCOVERY:338`) was not re-verified.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### INT-25
- **Claim ID**: INT-25
- **Domain**: production-fact
- **Intended state**: Production security findings exist and are catalogued elsewhere; reporting them to the owner is the correct disposition, with notification status open.
- **Repository-observed state**: **No record that the notification was sent** — identical lookup result to INT-13/SEC-32: zero send/notification confirmations across PROGRESS/DECISIONS/ROADMAP in either language. `S42_OPEN_QUESTIONS.md:39-40` still lists the E-group notification under "**아직 유효한 예외:**" (still-valid exception), and `:110` still lists it as one of only two currently-valid actions — the tracker itself treats it as outstanding.
- **Evidence**: `docs/S42_OPEN_QUESTIONS.md:39-40`, `:110`, `:94-104`; `docs/S42_DISCOVERY.md:199-268`; `docs/DECISIONS.md:9000-9005`, `:8928-8931`; `docs/PROGRESS.md:7726`; zero-hit send grep
- **Evidence type**: docs (negative grep)
- **Verification limitations**: Negative evidence.
- **Classification**: CONFIRMED_IN_REPOSITORY (no separate drift entry — the real-world consequence is carried by SEC-32's unsent-report family entry covering SEC-32/INT-13/INT-25)

#### INT-26
- **Claim ID**: INT-26
- **Domain**: org-comms
- **Intended state**: SUPERSEDED — ORG_ASKS' status table is stale post-D-152/D-153 against OPEN_QUESTIONS' ledger of message A/B/C/D dispositions.
- **Repository-observed state**: **Confirmed verbatim, unamended.** `S42_ORG_ASKS.md`'s status table still reads: **A** Timezone convention → "**Send now**" ("The only item that changes what gets built"); **B** DNS additions → "**Send now**"; **C** DB hosting + API reliability → "Hold until S42". Its internal notes still read "Message A is due **before S43 opens** ... and Message B before **S48**." The file's only dates are 2026-07-24/07-25 and it contains no D-152 or D-153 reference. Meanwhile `S42_OPEN_QUESTIONS.md:15-19` records C3/DNS as answered, C1·C2/timezone as closed by evidence, and Message A as downgraded to a courtesy question per D-153 §4.
- **Evidence**: `docs/S42_ORG_ASKS.md:7-14` (status table), `:386-389` (due dates), `:1-5` (dates); `docs/S42_OPEN_QUESTIONS.md:15-22`, `:108-113`; `docs/DECISIONS.md:9084-9097`, `:9122-9127`
- **Evidence type**: docs
- **Verification limitations**: Lookup only.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — **HIGH**: the status table says "Send now" for a message downgraded to courtesy (A) and one already answered (B), and dates A to "before S43 opens", a frozen session; acting on it sends the org an already-answered question)

#### INT-28
- **Claim ID**: INT-28
- **Domain**: org-comms
- **Intended state**: "Only two live actions" — the C3 half is superseded; the E-group half remains current.
- **Repository-observed state**: **Confirmed — the contradiction is live in all three places inside one file.** `:110` (under "## 지금 순서 (D-152 이후)") still reads "**C3(DNS) 발송**, **E그룹을 조직에 통지** — 이 둘만 지금 유효". `:76` still marks C3 **🔴** "**미룰 수 없음** — 순수 리드타임". Both are contradicted by `:17` in the same file: "**C3(DNS)** — **가능하다고 확인됨. 조직이 통합 시점에 추가해줌** → 더 이상 미결 아님". The D-153 ledger at `:15-19` is dated 2026-08-02; `:110`'s action list is dated to D-152 (2026-08-01) and was never updated.
- **Evidence**: `docs/S42_OPEN_QUESTIONS.md:17`, `:39-40`, `:74-78` (C3 row at `:76`), `:106-113`
- **Evidence type**: docs
- **Verification limitations**: None — all three statements are in one 121-line file, as the ledger says.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — **HIGH**: the same file states C3 answered-and-closed (`:17`) and urgent-undeferrable (`:76`, `:110`), and `:110` is the file's own "what to do now" list)

#### INT-29
- **Claim ID**: INT-29
- **Domain**: org-comms
- **Intended state**: The enrollment FAQ is still `status: draft`, the DRAFT banner is still in the content doc, and no approval landed.
- **Repository-observed state**: Confirmed, still draft. `knowledge-content/manifests/public.yaml:68-79` — `document_id: public-enrollment-faq`, `effective_from: "2026-08-01"`, `version: 1`, `status: draft` (line 78, exactly as the claim cites). The immediately preceding manifest entry shows `status: approved` at line 65, so the value is a live discriminator, not a default. The DRAFT banner is intact at `knowledge-content/documents/public/enrollment-faq/content.md:3-5`: "DRAFT — NOT APPROVED FOR PRODUCTION / Synthetic content for development and evaluation only. / This document is still in draft review and is not yet published." The four draft facts are present and unchanged: grades 1–7 in three bands skipping grade 3 ("early (1-2), middle (4-5), and upper (6-7)", `:9-10`) and "Enrollment happens through a branch manager" (`:14`).
- **Evidence**: `knowledge-content/manifests/public.yaml:68-79`; `knowledge-content/documents/public/enrollment-faq/content.md:1-15`
- **Evidence type**: content-state
- **Verification limitations**: The manifest `source_path` is `public/enrollment-faq/content.md` while the file lives at `knowledge-content/documents/public/enrollment-faq/content.md` — the claim cited `knowledge-content/public/...`, which does not exist; the loader presumably roots at `documents/`, which was not verified. Whether the *deployed* knowledge store still holds the draft is a runtime fact. The "sole launch-checklist gate" superlative would require reading the whole checklist and was not verified.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — LOW citation-precision note: the content doc lives under `documents/`)

#### INT-32
- **Claim ID**: INT-32
- **Domain**: integration
- **Intended state**: Token transport — our integration must use `x-access-token`, never `?token=`; verify once the O1b client exists.
- **Repository-observed state**: No O1b/icrest login client exists. Grep across `apps/`, `packages/`, `infra/` for `x-access-token`, `X-Access-Token`, `api/accounts/login`, `accounts/login` returns zero hits. The only `icrest` references are three prose comments in a time-zone helper documenting the legacy system's report offset — not a client.
- **Evidence**: negative grep as described; `packages/shared/src/intellichoice_shared/org_time.py:5`, `:60`, `:144` "fixed UTC{...} (matching icrest's reports)"
- **Evidence type**: negative grep
- **Verification limitations**: The requirement cannot be verified or violated until the client is built; absence is the expected state per the ledger.
- **Classification**: DEFERRED_BY_D152 (adjudicated centrally — compliance-by-absence confirmed; nothing violates yet)

#### INT-33
- **Claim ID**: INT-33
- **Domain**: deferred-work
- **Intended state**: §7 residual risks and assumptions — whether R1's org sign-off happened, and whether R8/R9 expiry is actively monitored.
- **Repository-observed state**: **Both negative.** (a) **R1 sign-off: no record** — the obligation appears once, at `INTEGRATION_PLAN.md:513` ("accepted, to be signed off by the org at S42 (discovery)"); a `sign.off|signed off` grep across DECISIONS/PROGRESS/INTEGRATION_PLAN/S42_SECURITY_REPORT returns nine hits, none related. Its occasion (S42 org interaction) is frozen by D-152. (b) **R8/R9 expiry: nothing monitors them** — per INT-22, the expiry conditions live only in INTEGRATION_PLAN §7, are duplicated into ARCHITECTURE.md *without* the expiry text, R8's named closures (S43/S46) are frozen, and R9's commit-ordering fix is recorded untouched. The reconciliation corpus has independently flagged this as HIGH (`DOCUMENTATION_RISK_REGISTER.md:108` — "The §7-R8/R9 accepted risks live in two places; only one carries the expiry").
- **Evidence**: `docs/INTEGRATION_PLAN.md:500-575` (`:513` R1, `:503-507` R8/R9 framing, `:535`, `:551-565`); `docs/ARCHITECTURE.md:605-609`; `docs/AUDIT_FINDINGS.md:71`; `docs/reconciliation/DOCUMENTATION_RISK_REGISTER.md:108`; `docs/DOCUMENT_INVENTORY.md:267, 324, 333, 378, 483`
- **Evidence type**: docs (negative grep)
- **Verification limitations**: Negative evidence on both halves. Terraform was not inspected by this inspector for a repairs-counter alarm — SEC-10 did so independently and confirms none exists.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — drift **HIGH**, covered by the one register entry spanning SEC-33, INT-22, INT-33, cross-linked to the G3/SEC-09 expiry-vs-freeze entry)

#### INT-35
- **Claim ID**: INT-35
- **Domain**: deferred-work
- **Intended state**: Six structural mismatches between the MySQL dev fake and production are catalogued, but D-152 withdrew the urgency because the mismatches provably stay behind the `ProfileAdapter` seam — `StudentProfile`/`BranchInfo`/`AttendanceStatus` being SPEC-derived, not fake-derived. Phase 3 must confirm no app-level decision depends on the fake's schema.
- **Repository-observed state**: The seam holds. All raw MySQL SQL — the fake's table and column names (`users.external_id/display_name/grade/branch_external_id/role`, `attendance.status/week_key`, `branches.manager_email/latitude/longitude`, `parent_child_links.child_external_id`) — is confined to `packages/adapters/src/intellichoice_adapters/mysql_profile_adapter.py`; grep for `FROM users|FROM attendance|FROM branches|FROM accounts` across `apps/` returns **zero** hits in app source. All 21 app-level consumption sites go through Protocol methods (`get_student_profile`, `get_parent_children`, `get_current_week_attendance`, `get_branch`, `list_branches`) and receive SPEC-derived Pydantic types. Attendance is derived inside the adapter (`row is None → AttendanceStatus.UNKNOWN`, else `AttendanceStatus(row.status)`), so the fake's status vocabulary is coerced at the seam. One boundary observation: `apps/learning-api/src/learning_api/services/attendance.py:7` imports `current_week_key` **from `intellichoice_adapters.mysql_profile_adapter`** — a module-level helper outside the `ProfileAdapter` Protocol — and uses its return value at `:103` as the `week_id` written into Postgres; the function itself delegates to `intellichoice_shared.org_time.resolve_org_time().week_key()`, i.e. it is SPEC/org-derived. Both apps construct `MySQLProfileAdapter` directly in `main.py` rather than behind a factory. `mysql-init` and the seed fixtures declare only four tables, whereas D-152 §3's S43 note describes `IcProfileAdapter` merging `org_branches` plus an `accounts` join — consistent with the catalogued mismatch.
- **Evidence**: `packages/adapters/src/intellichoice_adapters/mysql_profile_adapter.py:56-59,104-117,119-131`; `packages/shared/src/intellichoice_shared/profiles.py:7-51`; `apps/learning-api/src/learning_api/services/attendance.py:7`, `:103`; `apps/learning-api/src/learning_api/main.py:101`; `apps/chat-api/src/chat_api/main.py:78`; negative grep for MySQL table names in `apps/*/src`
- **Evidence type**: code + negative grep
- **Verification limitations**: Grep-based absence over `apps/*/src` `.py` files; a dependency expressed through a fixture-derived constant (e.g. a hardcoded `student-ext-N` id) would not surface, and test fixtures were not audited for the same coupling (the claim is about app-level modules).
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — orchestrator ruling on the escalation: D-152 §1's seam test is about SCHEMA/SHAPE dependence; every fake table/column name is confined to the adapter and all 21 call sites use Protocol methods plus SPEC-derived types. The `current_week_key` import edge crosses module boundaries but the value is org_time/SPEC-derived, so the seam's substance is intact. Drift LOW, housekeeping: the helper belongs in shared `org_time`, not the adapter module.)

### 3.7 WORK family — 33 claims

#### WORK-01
- **Claim ID**: WORK-01
- **Domain**: active-work
- **Intended state**: B6's `scope_guard`/retrieval overlap is specified, not built — no concurrent-`scope_guard` implementation exists in the graph.
- **Repository-observed state**: Confirmed absent. `apps/chat-api/src/chat_api/graph/build.py:170-232` wires a strictly sequential topology: `START → resolve_role → {scope_guard | prepare_admin_escalation}`, and `scope_guard`'s conditional edges (`:181-193`) are the only way into `answer_document_qa`, where retrieval happens (`nodes.py:463-498`). Every fan-out in the file is an `add_conditional_edges` mapping (one successor per turn), not a parallel fan-out; there is no `asyncio.gather`, no `Send`, no `defer`, and no retrieval call outside `answer_document_qa`/`explain_access`. `scope_guard` therefore completes — and its Bedrock round trip is paid — before any embedding or hybrid search runs.
- **Evidence**: `apps/chat-api/src/chat_api/graph/build.py:170-232`; `apps/chat-api/src/chat_api/graph/nodes.py:439-498`
- **Evidence type**: code + negative grep
- **Verification limitations**: None material; nothing executed.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### WORK-03
- **Claim ID**: WORK-03
- **Domain**: open-item
- **Intended state**: The `chat_escalation_sends` migration exists in the repo; only a deploy is needed to reach staging.
- **Repository-observed state**: The migration file exists — `packages/db/alembic/versions/8509c0486d8d_d421_chat_escalation_sends.py` — with a matching ORM model at `packages/db/src/intellichoice_db/models/chat_escalation_send.py`. The deploy pipeline's migration-before-switch ordering is corroborated by `deploy-staging.yml`'s "Deploy ops-task (patch image tag before running migrations against it)" step at `:157-166`, which precedes the service deploys at `:308-347`.
- **Evidence**: `packages/db/alembic/versions/8509c0486d8d_d421_chat_escalation_sends.py`; `packages/db/src/intellichoice_db/models/chat_escalation_send.py`; `.github/workflows/deploy-staging.yml:157-166`, `:308-347`
- **Evidence type**: code + CI config
- **Verification limitations**: Staging schema state is external → 3B.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — repo half confirmed; no drift)

#### WORK-04
- **Claim ID**: WORK-04
- **Domain**: open-item
- **Intended state**: The answer cache remains a decision, blocked on citation `effective_to`: citations carry `effective_to`, so a cached answer could outlive its sources; no answer cache exists.
- **Repository-observed state**: Split. **No answer cache exists** — the only `cache` constructs in chat-api and knowledge are `functools.lru_cache` on settings/dependency singletons (`config.py:194`, `dependencies.py:25`, `knowledge/settings.py:26`); no Redis/ElastiCache client, no answer-keyed store, no TTL logic. **The `effective_to` half is not literally true of the citation payload**: `effective_to` lives on `RagDocument`/`RagChunk` (`packages/db/src/intellichoice_db/models/rag.py:27`, `:60`) and is enforced as a retrieval predicate (`rag.py:79-82`), but the `Citation` model (fields document_title/document_version/page_number/section_title/source_reference/supporting_quote_hash) and the API's `CitationResponse` (`routers/sessions.py:130-136`) carry **no** `effective_to`. So the *sources behind* a citation carry an expiry; the citation object a cache entry would hold does not — the named fix ("clamp each entry's TTL to its earliest citation expiry") would need an extra lookup, which strengthens rather than weakens the "this is a decision, not an optimisation" conclusion.
- **Evidence**: as cited above
- **Evidence type**: code + negative grep
- **Verification limitations**: CDN/ALB caching (infra) not inspected; only application-level caching.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — for "no cache exists". LOW drift: PROGRESS's "citations carry `effective_to`" is imprecise — chunk/document rows do, citation DTOs do not.)

#### WORK-06
- **Claim ID**: WORK-06
- **Domain**: content-state
- **Intended state**: The cancel-endpoint defect (a post-deploy probe's 202-to-anonymous finding) was fixed by unscoping the sweep inside `request()`; it was not an authz bypass.
- **Repository-observed state**: Both halves confirmed in code. The sweep is now global: `packages/db/src/intellichoice_db/repositories/chat_turn_cancellation.py` `request()` — `pg_insert(...).on_conflict_do_nothing(...)` followed by `delete(ChatTurnCancellation).where(ChatTurnCancellation.requested_at < func.now() - STALE_AFTER)` with **no** `chat_session_id` predicate; the docstring states "**The sweep is global, and D-416 made it so after a live probe.** It used to be scoped to `chat_session_id` ... Measured on the deployed edge: `POST .../turns/probe/cancel` for an invented session answered 202. Unscoping the `WHERE` closes it without touching the authorization path". Auth/ownership order in the endpoint (`apps/chat-api/src/chat_api/routers/sessions.py:790-795`): `snapshot = await graph.aget_state(_graph_config(chat_session_id))` → `if snapshot.values: _assert_session_access(snapshot.values, claims)` → `await cancellations.request(...)` → `return Response(status_code=202)`. So ownership is checked *before* the write, but only when a checkpoint exists — an invented session id has no `snapshot.values`, so no owner exists to violate and the 202 stands by design (docstring: "this endpoint cannot tell a real session from an invented id, and it must not try"). `STALE_AFTER = timedelta(minutes=15)` against the 50s turn deadline.
- **Evidence**: `apps/chat-api/src/chat_api/routers/sessions.py:755-795`; `packages/db/src/intellichoice_db/repositories/chat_turn_cancellation.py` (module docstring, `request`, `is_requested`, `consume`)
- **Evidence type**: code
- **Verification limitations**: The staging deploy facts (run 32171998780, image tag `gha-44a12dfc9549`, rollout COMPLETED) are external to this repo and were not verified.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — code half; the deploy-state half is deferred to 3B, image tag and run id being external, with no separate drift)

#### WORK-07
- **Claim ID**: WORK-07
- **Domain**: known-limitation
- **Intended state**: The tfvars-floor warning was a phantom blocker corrected in place (D-418): renamed to `make image-check`; judges only a service vs its family's latest revision; reports the pin without failing on it; no longer demands a gitignored file; `adopt_deployed_image` defaults true since D-244.
- **Repository-observed state**: All confirmed. `image-check` exists in `.PHONY` and at `Makefile:292`; the target comment records the rename ("D-417 A3: renamed from `tfvars-floor-check`, because the tfvars floor is no longer the subject") and the measurement ("measured 2026-08-18: with the pin two deploys stale, `terraform plan` moved the image **forward** to what was running"), and states what the check still catches ("a service and its family's latest revision disagreeing, which is what anything resolving a family by name would run - `deploy-staging.yml` and the un-pinned EventBridge ops-task schedules both do (D-137)"). `adopt_deployed_image` default `true` at `variables.tf:213`. The script `scripts/check_deployed_image_consistency.py` is tracked, not gitignored.
- **Evidence**: `Makefile:1,280-294`; `terraform/environments/staging/variables.tf:201-214`; `scripts/check_deployed_image_consistency.py`; commit `899547f A3/D-418: the image floor already derived itself; the check was the defect (#340)`
- **Evidence type**: CI/build config + terraform config + git history
- **Verification limitations**: The stale "phantom blocker" text at `PROGRESS.md:85` / `OPEN_DECISIONS.md:15` is a docs matter outside this inspector's area; the script's runtime judgement is 3B.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — no new drift; the noted PROGRESS/OPEN_DECISIONS staleness is the ledger's own contradicts/competes entry)

#### WORK-08
- **Claim ID**: WORK-08
- **Domain**: open-item
- **Intended state**: Resolve whether D-401 (alarm split) and D-406 (NAT follows consumers) are "unblocked but unapplied" or "applied in W25".
- **Repository-observed state**: **Both are fully present in configuration, and both were committed well before the disputed date.** D-401: `aws_sns_topic.alerts_info` + `aws_sns_topic_subscription.alerts_info_email` exist; three alarms route to it; the enforcing test exists. D-406: `local.private_egress_consumers` + `needs_private_egress` exist and drive `nat_gateway_enabled`. Git history dates the *code* changes: `15bb6b3 W14: the NAT gateway follows its consumers, not one of them (#328)` (D-406) and `73e29c6 W8/W9: spend attribution needed a query, and the alarms are split by severity (#323)` (D-401), with `2e301d6 D-419: D-401/D-406 applied, and the refresh that nearly replaced a healthy audit bucket (#341)` recording the apply. So the config has contained both for several commits and a commit explicitly titled "applied" exists — consistent with ROADMAP W25 and inconsistent with `PROGRESS.md:155-156` — but a commit title is a *claim* of an apply, not the apply.
- **Evidence**: `terraform/modules/observability/main.tf:45-73`; `terraform/environments/staging/main.tf:100-138`; `git log --oneline` (15bb6b3, 73e29c6, 2e301d6)
- **Evidence type**: terraform config + git history
- **Verification limitations**: Applied-vs-unapplied is precisely a live-state question (`terraform plan` / AWS) → 3B. No terraform or aws command was run.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (adjudicated centrally — LOW drift: both D-401/D-406 are fully in config with a commit titled "applied" (2e301d6); `PROGRESS.md:155-156` is the likely-stale side. The apply itself is 3B.)

#### WORK-09
- **Claim ID**: WORK-09
- **Domain**: open-item
- **Intended state**: (observed-state claim) `.agents/skills/` and `skills-lock.json` are untracked and unignored, appearing in every `git status`.
- **Repository-observed state**: **The claim's observed state no longer holds — they are now tracked.** `git status --short` returns exactly one line: `?? docs/reconciliation/` (this audit's own directory). `git ls-files skills-lock.json .agents` returns `.agents/skills/agent-browser/SKILL.md` and `skills-lock.json` — both tracked. `.gitignore` contains no `skills`/`agents` pattern, so "not ignored" remains literally true but is no longer a problem. `git log -- skills-lock.json .agents` shows they were committed in `a6da941 D-417: twelve decisions recorded, and the video figure that was wrong by 100x (#338)`. On-disk `.agents` contains exactly one file, which is tracked.
- **Evidence**: `git status --short`; `git ls-files skills-lock.json .agents`; `.gitignore`; `git log --oneline -- skills-lock.json .agents`
- **Evidence type**: git history + code (gitignore)
- **Verification limitations**: None — this is directly observable. All git commands were read-only.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally, from the inspector's CONTRADICTED — MEDIUM: `PROGRESS.md:158-160` records the commit-vs-ignore user choice as open for paths already committed in a6da941/D-417. This REFUTES Phase-2 WORK-09 as CURRENT; correspondingly `PROGRESS.md:83`'s "agent tooling committed ✅ done" is now the accurate line.)

#### WORK-11
- **Claim ID**: WORK-11
- **Domain**: open-item
- **Intended state**: Resolve C8 `ruff format`'s contradictory status ("⏳ next / 168 of 494" vs done / 168 of 437), the denominator, whether `ruff format --check` is wired into CI and/or `make lint`, and where the mechanical commit is.
- **Repository-observed state**: **ROADMAP is right on all three counts, and its 437 is exactly reproducible; PROGRESS's 494 matches nothing.** Mechanical commit: `5728b95 style: ruff format, mechanically, across 168 Python files (D-417/C8)` — `git show --numstat` confirms **exactly 168 files changed**, 795 insertions / 1118 deletions, a pure-format commit. Enforcement landed separately: `f0d2cfe build: enforce ruff format, in CI as well as in make lint (D-417/C8)`. Denominator: at 5728b95 the repo had **473** tracked `.py` files; `[tool.ruff] extend-exclude = ["packages/db/alembic/versions"]` removes **36** → **437**, exactly ROADMAP's number. At HEAD: 477 tracked `.py` (packages 267, apps 168, scripts 40, load-tests 2) → 440 ruff-visible. No count in repo history plausibly yields 494. Wiring: both places — `Makefile:120-124` → `lint: uv run ruff check . ; uv run ruff format --check .` (with "`format --check` rather than `format`, so `make lint` never rewrites files as a side effect of asking a question"), and `.github/workflows/ci.yml:81-82` → a dedicated "Format check" step ("formerly enforced here as well as in `make lint`, because this job - not the Makefile - is what the branch-protection rule requires"). Markdown scoped out as ROADMAP says: `[tool.ruff.format] exclude = ["*.md"]`, formatter-only.
- **Evidence**: `git show --stat 5728b95`; `git ls-tree -r --name-only 5728b95 | grep -c '\.py$'` → 473; `git ls-files 'packages/db/alembic/versions/*.py' | wc -l` → 37 (36 at that commit); `pyproject.toml:24-40`; `Makefile:120-127`; `.github/workflows/ci.yml:74-82`
- **Evidence type**: git history + CI config + code (Makefile, tool config)
- **Verification limitations**: None material. Whether the branch-protection rule actually requires the job is a GitHub-settings fact → 3B.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — for ROADMAP's version: C8 is DONE (5728b95, exactly 168 files), denominator 437 exactly reproduced, enforcement in both `make lint` and CI. MEDIUM drift: `PROGRESS.md:84`'s "⏳ next / 168 of 494" is stale in status AND denominator (494 unreproducible); treat the whole four-row queued block (A3/B4/B6/C8) as superseded. Resolves the Phase-2 contradiction in ROADMAP's favour.)

#### WORK-12
- **Claim ID**: WORK-12
- **Domain**: open-item
- **Intended state**: learning-web's disconnect-banner render condition has no test; chat-web's does.
- **Repository-observed state**: Confirmed. learning-web has four unit test files (`components/ConnectingPanel.test.tsx`, `lib/attendanceLabels.test.ts`, `lib/masteryBands.test.ts`, `api/stream.test.ts`); grep for `banner|streamState` across them yields one hit, and it is prose inside a test title in `stream.test.ts:148`, not an assertion on the render condition. No e2e learning spec mentions `stream-banner` or `streamState` (grep over `e2e/tests/learning/` returns nothing). chat-web by contrast has `screens/ChatScreen.test.tsx` (17 `banner|streamState` matches) plus the browser spec `e2e/tests/chat/stream-disconnect-visible.spec.ts`. The condition itself is `session.streamState === "error"` inline in `apps/learning-web/src/App.tsx:977-984`, inside `renderContent`'s branch order — matching the claim's "both inside App.tsx's render logic".
- **Evidence**: `apps/learning-web/src/App.tsx:947-984` (comment block and the `streamBanner` expression), `:958-960`; test-file inventory for both apps; `e2e/tests/chat/stream-disconnect-visible.spec.ts`; `docs/PROGRESS.md:107-117`
- **Evidence type**: negative grep (test inventory) + code (in-code commentary) + docs
- **Verification limitations**: Absence of a test is established by name/keyword grep over the four learning-web test files and the learning e2e directory; a test asserting the condition without using either word would be missed (unlikely given the tokens).
- **Classification**: CONFLICT (adjudicated centrally — MEDIUM: `App.tsx:958-960` reads "**This condition is deliberately untested, and that is a decision rather than an oversight (D-417 / C7). Do not re-file it as missing coverage.**" while `PROGRESS.md:107-117` carries it as open after W21 ("still open after W21... price the real work or leave it"). Two live statuses for one gap; both cited, neither retracted. Likely PROGRESS lagging, but D-417/C7's scope (chat vs learning) must be settled from the D-417 text.)

#### WORK-13
- **Claim ID**: WORK-13
- **Domain**: open-item
- **Intended state**: The ledger records UNKNOWN for `journey-student.spec.ts`'s isolation against staging; the named test-side fixes were a per-test fixture student or a `beforeEach` session clear.
- **Repository-observed state**: The per-test-fixture fix is present. `e2e/tests/learning/journey-student.spec.ts:117` signs in as `FIXTURES.studentJourney` with the comment "**Its own student, not `studentPresent`** (D-365 §2). This walk named the isolation finding `config.ts` states"; `:427` signs in as `FIXTURES.studentResume` with "Its own student, NOT studentPresent (D-288). Staging's sessions persist, so a second test signing in as the full walk's student resumes that walk's exam mid-flight". `e2e/config.ts:128-165` defines `studentPresent` (`student-ext-1`), `studentResume` (`student-ext-9`) and `studentJourney` (`student-ext-10`), with a comment recording that this walk "was the last one still sharing `studentPresent` with seventeen other spec files". No `beforeEach` and no session-clearing hook appears in the spec (the only `test.describe.configure` is a 300 s timeout at line 26) — so the first of the two named fixes was applied, the second was not.
- **Evidence**: `e2e/tests/learning/journey-student.spec.ts:110-117`, `:421-427`; `e2e/config.ts:128-165`
- **Evidence type**: test-source
- **Verification limitations**: Whether the isolation defect is actually resolved cannot be confirmed — that was a measured three-run staging observation and tests were not executed. Whether the staging e2e run is still a gate: `.github/workflows/ci.yml` typechecks the e2e harness but its comment states "Running the browser suite itself needs live app servers, so it stays out of CI", i.e. not a CI gate.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — per-test fixture students present per D-365 §2/D-367; `studentJourney=ext-10`, `studentResume=ext-9`. Resolves the ledger UNKNOWN. LOW-MEDIUM doc note: PROGRESS's physically last entry (2026-08-07) is stale; the behavioural re-measure is 3B.)

#### WORK-14
- **Claim ID**: WORK-14
- **Domain**: deferred-work
- **Intended state**: D-342 parks all question-bank coverage work until the user asks — a standing instruction, not a per-session deferral; every coverage item (depth, missing tiers, thin banks, skills with no video) is parked. (§9 marked this claim evidence-complete; it was inspected anyway.)
- **Repository-observed state**: Consistent with a parked content state. `curriculum/internal_math/skills.yaml` declares **112** skills; `curriculum/internal_math/topics.yaml` declares **33** topics; `curriculum/internal_math/authored/` holds **33** bank files with **958** items total. Nothing in the repository attempts to narrow a declaration or threshold to close a gap — `grade_topic_mapping.yaml:6-8` explicitly says "Only grade bands with a seeded topic are populated below... the rest are added as topics are authored for them", and `:26-29` forbids adding a "3-4" band to paper over a gap, pinned by `test_adding_a_band_never_steals_a_grade_from_an_existing_one`.
- **Evidence**: `curriculum/internal_math/skills.yaml` (112 `skill_id:` entries); `curriculum/internal_math/topics.yaml` (33 topics); `curriculum/internal_math/authored/` (33 files, 958 `question_template_id:` entries); `curriculum/internal_math/grade_topic_mapping.yaml:1-38`
- **Evidence type**: content-state
- **Verification limitations**: The claim's four figures (84 of 153 cells, 189 items short, ≈$13–16, ~3.5 h, 15 of 96 spanning skills, 5 skills at 1–3 items, 10 of 112 skills with no video) are derived measurements over a live database; the video figures in particular are DB-only and unverifiable from files. Only the denominators (112 skills, 33 topics) and the total item count were verified. A "standing instruction" is a documentary fact, not a code fact.
- **Classification**: CONFIRMED_IN_REPOSITORY (as a parking decision and content state; the specific derived counts remain UNVERIFIED)

#### WORK-15
- **Claim ID**: WORK-15
- **Domain**: known-limitation
- **Intended state**: Anything not about content *quantity* stays a defect despite D-342; the parking depends on one tested behaviour — `_closest_to_recommended` never returns empty, so an unstocked tier stays servable.
- **Repository-observed state**: The test exists and is driven from the real taxonomy rather than a fixture. `apps/learning-api/tests/test_study_plan_difficulty_routing.py:250-274` — `test_every_declared_tier_of_every_spanning_skill_is_servable`, docstring "**The property the taxonomy decision rests on.**", enumerates every spanning skill from `load_curriculum()` (`:240-248`), constructs the worst case (a bank holding one tier, as far from the recommendation as the declaration allows), and asserts `got` non-empty with the message "that tier is a dead end". The vacuity guard is present: `assert spanning, "the curriculum has no spanning skills - this test would be vacuous"` (`:262`), and the companion `test_an_exactly_matching_tier_still_wins_over_a_nearby_one` (`:277-285`) exists so a function that always returned the whole pool cannot pass trivially. The fallback it pins is at `apps/learning-api/src/learning_api/services/study_plan.py:65-160`. Also present: `test_falls_back_to_the_whole_pool_rather_than_serving_nothing` (`:86`), `test_a_fully_used_skill_still_serves_rather_than_failing` (`:196`).
- **Evidence**: `apps/learning-api/tests/test_study_plan_difficulty_routing.py:69-285`; `apps/learning-api/src/learning_api/services/study_plan.py:65-160`
- **Evidence type**: test-source + code
- **Verification limitations**: Existence and assertion strength verified; pass status not (TEST_EXISTS_NOT_EXECUTED limitation). The claim's other half (a wrong answer key or an item contradicting its own judge rating remains a defect) is a policy statement with no code assertion.
- **Classification**: CONFIRMED_IN_REPOSITORY (carries a TEST_EXISTS_NOT_EXECUTED limitation as written)

#### WORK-18
- **Claim ID**: WORK-18
- **Domain**: known-limitation
- **Intended state**: (from `docs/ROADMAP.md:3313-3317`) W27's three code-verified constraints — (1) retrieval's input is written before `scope_guard`; (2) `QAState` holds chunk **ids not bodies**, so the answer node must re-fetch; (3) every non-`document_qa` turn would pay one wasted rerank.
- **Repository-observed state**: All three verified. (1) `resolve_role` writes `"standalone_query": ctx.query` (`graph/nodes.py:312`) and is the node every turn enters first (`build.py:170`), while `scope_guard` only reads it (`nodes.py:469`, `assert state.standalone_query is not None`). (2) `QAState.retrieved_chunk_ids: list[str] | None` with the comment "External chunk ids only, not full chunk bodies" (`graph/state.py:68-70`); `answer_document_qa` stores `[chunk.chunk_id for chunk in retrieval.chunks]` (`nodes.py:495-498`) and `synthesize_answer` re-fetches via `ctx.rag_repo.get_chunks_by_ids(chunk_ids)` (`nodes.py:526-528`), its docstring stating "re-loaded by id - `QAState` checkpoints ids only, never full chunk bodies". (3) `retrieve()` always issues the `BedrockTask.RERANK` call after the hybrid search (`packages/knowledge/src/intellichoice_knowledge/retrieval.py:341-359`) and `intent` is only known after `scope_guard` returns (`nodes.py:393-397`), so speculatively running retrieval in parallel would pay one embedding plus one rerank on every `admin_contact`/`calendar`/`branch_locator`/out-of-scope turn.
- **Evidence**: as cited above; `docs/ROADMAP.md:3304-3320` for the constraint text
- **Evidence type**: code + docs
- **Verification limitations**: The latency numbers themselves (4124/3411/2129/124 ms) were measured on staging and are not re-derivable from this repo → 3B.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — all three constraints; the latency numbers are 3B)

#### WORK-19
- **Claim ID**: WORK-19
- **Domain**: open-item
- **Intended state**: (U7 §9.1) The retention age floor has not been chosen.
- **Repository-observed state**: **The floor has been chosen and is in code — three floors, not one.** `checkpoint_retention_cli.py` sets `COMPLETED_RETENTION_DAYS = 30`, `ABANDONED_RETENTION_DAYS = 90`, `CHAT_RETENTION_DAYS = 180`, with a documented rationale table and the D-331 byte measurement (completed 1.7%, abandoned 77%, chat 19%). Deletion is **dry-run by default**: `apply_enabled()` returns True only for an explicit `CHECKPOINT_RETENTION_APPLY=true`. Per-run bounds exist (`MAX_THREADS_PER_RUN` 500, `MAX_SPEND_CENTS` 100). The job is **not scheduled** — absent from `terraform/modules/scheduled-jobs/main.tf`'s `locals.jobs`, and the `session-consolidate` entry explains why.
- **Evidence**: `apps/learning-api/src/learning_api/services/checkpoint_retention_cli.py:88-90` (the three constants), `:19-24` (windows table, "completed learning | 30 days | SPEC's own number"), `:5-7` ("**Dry-run unless `CHECKPOINT_RETENTION_APPLY=true`.** A job whose failure mode is silently deleting a K-12 student's learning history does not get to delete by default"), `:97-99`; `terraform/modules/scheduled-jobs/main.tf:46-51`; `grep -rn "checkpoint_retention" terraform/` → no matches
- **Evidence type**: code + terraform config (negative)
- **Verification limitations**: The choice's *documentation* status (whether DECISIONS.md/U7 §9.1 was updated) was outside this inspector's reading — see WORK-22. Terraform absence proves the job is not defined in config, not that no operator runs it by hand. The dry run was not executed, so "reports zero eligible threads at 30/90/180" is unverified.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — the ledger/U7 §9.1 "floor not chosen" is refuted: 30/90/180 are chosen in code per D-333. Plus a policy-without-enforcement drift, MEDIUM: the job is unscheduled and dry-run by default — a retention promise over minors' data that no job is scheduled to keep.)

#### WORK-20
- **Claim ID**: WORK-20
- **Domain**: open-item
- **Intended state**: (U7 §9.2) Does `learning_sessions` get built now?
- **Repository-observed state**: **Built.** Migration `6538a95bc990_d331_learning_sessions.py` creates the table with five indexes and sits in the live chain (`down_revision = "d4b81f6c2e70"`, and `4cfc45b7c5ff_d333_memory_consolidated_at.py` has `down_revision = "6538a95bc990"`), and a SQLAlchemy model exists. The earlier `f3d82932ed10_drop_learning_sessions_superseded_by_.py` is **not** a later reversal — it revises `05a193bc739b` (2026-07-15) and drops the S5 stand-in table, long before the D-331 re-creation. A producer exists (`session_consolidation_cli` → `LearningSessionRepository.upsert`) and is a **scheduled, enabled** job.
- **Evidence**: `packages/db/alembic/versions/6538a95bc990_d331_learning_sessions.py:26-34`; `packages/db/alembic/versions/4cfc45b7c5ff_d333_memory_consolidated_at.py:27`; `packages/db/src/intellichoice_db/models/learning_session.py:50-51`, `:87`, `:100`; `packages/db/alembic/versions/f3d82932ed10_drop_learning_sessions_superseded_by_.py:5,21`; `terraform/modules/scheduled-jobs/main.tf:52-60`
- **Evidence type**: migration source + code + terraform config
- **Verification limitations**: Migration presence in the chain does not prove it has been applied to any deployed database (no DB inspected). Terraform `enabled = true` is config, not a deployed schedule.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — migration 6538a95bc990 in the live chain plus model plus scheduled producer; resolves the ledger UNKNOWN. U7 §9.2's still-open question is documentation drift in the U7 doc, already registered in Phase 1/2 — cross-referenced, not re-filed.)

#### WORK-21
- **Claim ID**: WORK-21
- **Domain**: known-limitation
- **Intended state**: (U7 §9.3) Chat checkpoints are unbounded, addressed by no policy.
- **Repository-observed state**: **A chat-checkpoint retention policy is implemented** — the 180-day inactivity window of D-333, inside the same `checkpoint_retention_cli`. `_process_chat_threads` deletes `checkpoint_writes`/`checkpoint_blobs`/`checkpoints` for threads past the cutoff, and `_chat_thread_ids` classifies "chat" by two positive conditions (no `learning_sessions` row **and** no `phase` key in any of the thread's checkpoint `channel_values`) specifically so an unprojected learning thread cannot be deleted under the chat policy. Deletion is dry-run by default (same `CHECKPOINT_RETENTION_APPLY` gate; the dry-run path records `would_delete_chat`). Chat consolidation is documented as a structural no-op, and `interrupt_approvals` rows are deliberately retained past thread deletion.
- **Evidence**: `apps/learning-api/src/learning_api/services/checkpoint_retention_cli.py:90` `CHAT_RETENTION_DAYS = 180`; `:23`; `_chat_thread_ids` docstring — "**Two conditions, because one of them is not enough.**... if the reconciler had never run, every learning thread past 180 days would be deleted here - under the chat policy, bypassing the consolidation gate entirely", SQL `NOT EXISTS (... learning_sessions ...)` AND `NOT EXISTS (... p.checkpoint->'channel_values' ? 'phase')`; `_process_chat_threads` — `if not apply: counts.note("would_delete_chat"); continue`; `:28-34`; `grep -rn "checkpoint_retention" terraform/` → no matches
- **Evidence type**: code (including raw SQL) + terraform config (negative)
- **Verification limitations**: Not executed; the SQL's correctness against real checkpoint JSON shape is unverified. Because the job is unscheduled and defaults to dry-run, chat checkpoints are **in practice still unbounded**. The 2,178 threads / 35.6 MB figures are unverifiable read-only.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — the 180-day chat policy is implemented with a two-condition classifier but is NOT scheduled and is dry-run by default, so chat checkpoints in practice remain unbounded. MEDIUM; same decision as WORK-19.)

#### WORK-22
- **Claim ID**: WORK-22
- **Domain**: open-item
- **Intended state**: (U7 §9.4) Unknown whether a follow-up session for abandoned-session retention was scheduled.
- **Repository-observed state**: **No follow-up session was scheduled — because the recommendation was adopted directly, one day later, by D-333.** U7's §9.4 (2026-08-14) asks "Abandoned sessions (§8.3) — you scoped them out... Worth revisiting as its own session?" and §8.3 recommends a 90-day floor. D-333 (2026-08-15) records the user's decision in their own words: "Keep both chat and abandoned/pending checkpoints on a 90-day inactivity retention window", and its three-window table gives completed **30 days** / abandoned-pending **90 days** inactivity / chat **180 days** inactivity. PROGRESS confirms "**✅ U7 IS COMPLETE (2026-08-15, D-333)**", merged (`8c86685`, #274) and deployed, dry-run unless `CHECKPOINT_RETENTION_APPLY=true`. **`U7_CHECKPOINT_CONSOLIDATION.md` itself was never updated** — its Status line still reads "design review, **measured**. Steps 1–2 of §8 are done; no deletion code written", and §9's four open items are still posed as open questions.
- **Evidence**: `docs/U7_CHECKPOINT_CONSOLIDATION.md:1-5` (stale status), `:52-63`, `:265-279` (§8.3), `:281-292` (§9); `docs/DECISIONS.md:23837-23860` (D-333, user's words at `:23843`, table at `:23858`); `docs/PROGRESS.md:1238-1247`
- **Evidence type**: docs
- **Verification limitations**: Only D-333's opening block was read, not the full decision; whether every one of §9's four items was resolved there is not fully established (items 1, 3 and 4 clearly were; item 2, `learning_sessions`, is not covered by the lines read — see WORK-20, which resolves it independently).
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — MEDIUM: U7's §9.4 question was answered next-day by D-333 (30/90/180 windows, shipped and deployed) and the U7 doc was never updated and carries no completion banner. Resolves the ledger UNKNOWN and corroborates the WORK-19 floors ruling.)

#### WORK-24
- **Claim ID**: WORK-24
- **Domain**: known-limitation
- **Intended state**: (U7 §10) Unknown whether a later decision or session investigated the duplicate-`learning_gain` path.
- **Repository-observed state**: **It was investigated and closed — twice over.** D-336 (2026-08-15) chased it: "D-331 noticed one staging thread with two `learning_gain` rows and recorded it as out of scope. Chased now, it is a real parent-visible defect with a one-line cause." Cause: `POST /exam/finalize` carries no `Idempotency-Key` (only `/answers` does), so a retry/double-submit/reconnect recomputes and re-inserts — two byte-identical rows 46 seconds apart, and `services/history.py` returned 10 session summaries for 9 real cycles. Status: "cause fixed; **the existing duplicate row is left alone** (a deletion, and therefore the user's call)". A later PROGRESS entry closes the carry-over by measurement: "**The `98abc0f0` double-`learning_gain` carry-over is closed by measurement**: staging holds **9 gain rows and 0 duplicate pre-assessment ids**, so D-336's migration had already removed it." **U7 §10 still reads "Out of U7's scope and recorded as a carry-over rather than investigated here"**, with no pointer to D-336.
- **Evidence**: `docs/U7_CHECKPOINT_CONSOLIDATION.md:291-297` (unchanged); `docs/DECISIONS.md:24160-24185` (D-336); `docs/PROGRESS.md:976-977`, `:1080`, `:2356`
- **Evidence type**: docs
- **Verification limitations**: D-336 names `pre=f422de5d...` as the duplicate while U7 §10 names thread `98abc0f0...` — a thread id vs a pre-assessment session id, consistent but not identical identifiers; `PROGRESS:976` explicitly ties the `98abc0f0` carry-over to D-336's migration, which is what links them.
- **Classification**: DOCUMENTATION_DRIFT (adjudicated centrally — LOW: the duplicate-gain path was investigated and closed by D-336 plus closed-by-measurement (9 rows, 0 duplicates); U7 §10 still says un-investigated. Resolves the ledger UNKNOWN.)

#### WORK-26
- **Claim ID**: WORK-26
- **Domain**: known-limitation
- **Intended state**: QUESTION_GENERATION's trailing "Next:" is a superseded plan naming a non-Anthropic model; no Mistral configuration exists in the pipeline.
- **Repository-observed state**: **No Mistral model id is configured anywhere.** Repo-wide grep across `*.py`/`*.yaml`/`*.yml`/`*.toml`/`*.example`/`*.tf`/`*.json` (excluding `.venv`) yields five hits, all non-configuration: three are prose comments citing `mistral-large-3` as historical measurement evidence for a *rejected* behaviour (`packages/curriculum/src/intellichoice_curriculum/review_loop.py:251`, `hint_solution_repair.py:138` "`mistral-large-3` rewrote **every** solution step", `packages/curriculum/tests/test_review_loop.py:267`), and two are adapter test assertions about capability detection (`packages/adapters/tests/test_bedrock_provider.py:12` asserting `not _supports_prompt_caching("mistral.mistral-large-3-675b-instruct")`; `test_bedrock_gateway.py:749`). `.env.example` and `packages/curriculum/.../settings.py` contain zero Mistral references. The stale instruction is still in the doc at `docs/QUESTION_GENERATION.md:449`.
- **Evidence**: greps above; `docs/QUESTION_GENERATION.md:446-450` (stale "Next:") vs `:243-282` (superseding roster); `.env.example:26-39`; `packages/curriculum/src/intellichoice_curriculum/settings.py:23-33`
- **Evidence type**: negative grep + docs
- **Verification limitations**: None material — a clean absence result. `.env.example` is a template; the operative `.env` was not read.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — supersession confirmed; zero Mistral config anywhere. **MEDIUM drift**: `QUESTION_GENERATION.md:449`'s trailing "Next:" still instructs a Mistral-Generator course of action, contradicting `:243-282` of the same file and matching nothing in code.)

#### WORK-27
- **Claim ID**: WORK-27
- **Domain**: known-limitation
- **Intended state**: (per `docs/QUESTION_GENERATION.md:266-271`) Only two Anthropic models are invocable, so Solver B shares the Generator's weights: Generator = `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, Solver A = `us.anthropic.claude-haiku-4-5-20251001-v1:0`, Solver B = Sonnet 4.5, Judge = Haiku 4.5.
- **Repository-observed state**: The slot→role mapping is confirmed in code, but **the configured ids do not match the documented roster and the sharing pair is different.** Mapping: `ai_pipeline.py:967-968` ("authored solvers deliberately reuse the shape pipeline's `QUESTION_GENERATION` and `QUESTION_REVIEW` task slots so they resolve to two different models") plus call sites `:1329` `AUTHORED_QUESTION_GENERATION` = Generator, `:1911` `QUESTION_GENERATION` = Solver A, `:1923` `QUESTION_REVIEW` = Solver B, `:1970` `QUESTION_JUDGE` = Judge; corroborated by `pipeline_cli.py:732-734`. `.env.example:28-37` therefore configures **Generator = Haiku 4.5, Solver A = Haiku 4.5, Solver B = Sonnet 4.5, Judge = Haiku 4.5** — Generator sharing with **Solver A**, not Solver B, the mirror image of the documented roster. `packages/curriculum/src/intellichoice_curriculum/settings.py:23-33` defaults all four slots to `anthropic.claude-sonnet-5`, the id D-273's 1-token probe measured as **AccessDenied**. The preflight guard the pigeonhole argument rests on is real and fail-closed: `pipeline_cli.py:735-745` compares `underlying_model(solver_a) != underlying_model(solver_b)` and fails with "Solver A and Solver B ... their agreement would be one opinion counted twice", including the two-inference-profiles-for-one-model case, with tests at `test_authored_pipeline.py:1428` and `:1457`.
- **Evidence**: `.env.example:10-39`; `packages/curriculum/src/intellichoice_curriculum/settings.py:16-33`; `ai_pipeline.py:967-968, 1247, 1329, 1911, 1923, 1970`; `pipeline_cli.py:732-745`; `docs/QUESTION_GENERATION.md:243-282`
- **Evidence type**: code + test-source
- **Verification limitations**: `.env.example` is a template, not the operative configuration; the real `.env` is FORBIDDEN to read and stays unread, so **the operative roster is unresolvable in 3A — and not resolvable by 3B either without the user.** Model invocability is an AWS account fact re-measurable only live, and the claim itself carries an expiry. The open cost question ("was the cost-per-accepted-item measurement ever taken?") could not be confirmed: no `scripts/measure_*` is named for it.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — structural halves confirmed (two invocable models, pigeonhole, fail-closed preflight and both tests). **MEDIUM drift**: `.env.example:28-37` configures the MIRROR of the documented roster, so the documented "better Generator" gain is not what the example configures; and `settings.py:23-33` defaults all four slots to an id measured AccessDenied (D-273). Escalation ruling: record the drift against `.env.example` plus the doc, and mark the operative roster unresolvable in 3A.)

#### WORK-28
- **Claim ID**: WORK-28
- **Domain**: known-limitation
- **Intended state**: HINT_SOLUTION_REVIEW — `review_panel.py`, `hint_solution_repair.py` and `review_loop.py` all exist and are implemented; the header's "the loop around them is not built" is in tension with that; "Still not built: any pipeline caller."
- **Repository-observed state**: The internal contradiction resolves in the code's favour — **all three modules exist and are implemented, and there is no pipeline caller.** `review_panel.py` (`review_panel` at `:111`), `hint_solution_repair.py`, and `review_loop.py` (`run_review_loop` at `:131`, calling `review_panel` at `:191` and returning `LoopOutcome("accepted", ...)` on unanimity at `:209`) are all present. So "the loop ... is not built" is false as written. The pipeline-caller claim is **exactly true**: the only non-test, non-self importers are scripts — `scripts/repair_authored_solutions.py:35` `from intellichoice_curriculum.review_loop import run_review_loop`, invoked at `:211`; also `scripts/apply_solution_repairs.py:34` and `scripts/measure_hint_solution_review.py:59,72`. Grep for `HINT_SOLUTION`, `review_loop`, `review_panel`, `hint_solution` against `ai_pipeline.py` and `pipeline_cli.py` returns **zero hits** in both. Residual inaccuracy: `review_loop.py:3` ("**Nothing calls this.**") and `review_panel.py:5-6` ("the repair loop ... [is] not built") are stale, since `scripts/repair_authored_solutions.py:211` does call `run_review_loop` and `review_loop.py` sits beside `review_panel.py`.
- **Evidence**: directory listing of `packages/curriculum/src/intellichoice_curriculum/`; `review_loop.py:1-15, 35-40, 131, 191, 209`; `hint_solution_repair.py:1-10`; `review_panel.py:1-15, 37, 111`; `scripts/repair_authored_solutions.py:35, 211`; zero-hit grep over `ai_pipeline.py` + `pipeline_cli.py`; `docs/HINT_SOLUTION_REVIEW.md:1-18`
- **Evidence type**: code (import-graph analysis, positive and negative)
- **Verification limitations**: "No pipeline caller" verified by grep over the two pipeline modules and the whole-repo import graph; a dynamic/reflective call would evade this, though nothing suggests one. Whether the script has ever been *run* is not a repository fact.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — for the operative halves: instrument built, NO pipeline caller. Resolves the ledger UNKNOWN: the loop module IS built. **MEDIUM drift ×2**: (a) `HINT_SOLUTION_REVIEW.md`'s header "the loop around them is not built" is contradicted by `review_loop.py`'s existence and should read "built but uncalled"; (b) in-code docstrings are stale in the same direction.)

#### WORK-30
- **Claim ID**: WORK-30
- **Domain**: content-state
- **Intended state**: `route_answer` verifiers for `selection`/`multi_root`/`interval`/`tuple`/`symbolic` landed with Phase R (D-273), fail-closed, both-directions tested — superseding CONTENT_COVERAGE's "⚠️ needs the Phase R answer-model router" cell.
- **Repository-observed state**: The router landed and is fail-closed, with one naming caveat and two figure corrections. `route_answer` (`packages/curriculum/src/intellichoice_curriculum/authored_validation.py:746-785`) is explicitly fail-closed: "**Fail closed:** a form no model claims is an error, never a skip - an item whose answer nothing can check must not reach a student on the strength of nobody having checked it." Four of the five named models are real `DerivedAnswer` kinds: `multi_root` (`:870`), `interval` (`:888`), `tuple` (`:942`), `symbolic` (`:785`), plus `value` (`:869`); matching for each is in `_option_matches` (`:994-1060`). **`selection` is not a distinct answer model** — grep for `"selection"`/`'selection'` across `packages/curriculum` returns zero hits; comparison questions are expressed through the **`value`** model (`packages/curriculum/tests/test_answer_model_router.py:40-43` parametrizes `("Eq(x, Max(34, 43))", "value")` with "It is `value` because the answer *is* a value - the point is that `Max` does the selecting"; likewise `("Eq(x, gcd(12, 18))", "value")`). Both-directions testing exists (`:53`, `:70`, `:112`, `:136`, `:146`, `:341`). `place_value_compare` is re-authored: 15 items carry that `skill_id` in `place_value.yaml`, matching D-273's "15/15". Family C is no longer gated: 40 items carry a non-null `figure_spec` across the bank (of 958), and the gate covers them via `check_figure_agrees_with_the_question` / `check_reading_matches_the_figure` (`:1778`, `:1816`, both wired into `validate_authored_item`). **The band figure has moved**: CONTENT_COVERAGE records 4 of 12 grade bands populated; `grade_topic_mapping.yaml:39-99` now populates **seven** (`"1-2"`, `"2-3"`, `"4-5"`, `"6-7"`, `"8-9"`, `"10-11"`, `"11-12"`). The band-order trap is real and documented at `:26-29`, pinned by `test_adding_a_band_never_steals_a_grade_from_an_existing_one`.
- **Evidence**: `authored_validation.py:746-785, 869-942, 994-1060, 1778, 1816, 1862-1901`; `packages/curriculum/tests/test_answer_model_router.py:30-146, 341-412`; `curriculum/internal_math/grade_topic_mapping.yaml:26-29, 39-99`; `curriculum/internal_math/authored/place_value.yaml`; `curriculum/internal_math/authored/plane_figures.yaml:4-29`; `docs/CONTENT_COVERAGE.md:96, 98, 102, 165, 169`
- **Evidence type**: code + test-source + content-state
- **Verification limitations**: The 37-row family-B census and the 34-row family-C count are derived from a build script over a live DB (`scripts/build_content_coverage.py`) and were not re-derived; the *verifier* coverage was verified rather than the row-by-row mapping. "Both-directions tested" verified by test existence and parametrization, not execution.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — supersession of the family-B cell confirmed: `route_answer` fail-closed, five models matched, both-directions tests exist; family C authored and gated; `place_value_compare` 15/15. **MEDIUM drift ×2**: (a) `CONTENT_COVERAGE.md:96/:165` still shows family B as needing Phase R, superseded same-day by D-273; (b) its content-state figures are stale in three places (4→7 of 12 grade bands; family C authored not gated). LOW: `selection` exists in the doc as an answer model the code never implements under that name, folded into `value` via Max/gcd.)

#### WORK-31
- **Claim ID**: WORK-31
- **Domain**: user-decision
- **Intended state**: The volume target is 5–7 items per occupied tier, chosen over SPEC §5.8.1 as a deliberate, recorded departure (D-223).
- **Repository-observed state**: **SPEC §5.8.1 still says 100, with no amendment marker.** `## 5.8 Question Bank and AI Generation/Review Pipeline` → `### 5.8.1 Question Volume` reads "Each topic contains 100 validated base templates:" followed by the fenced block `Difficulty 1: 20 templates` through `Difficulty 5: 20 templates`, then "Each template can generate multiple numerical variants." There is no D-223 reference, no strikethrough, no superseded banner, and no cross-reference to CONTENT_COVERAGE.
- **Evidence**: `docs/SPEC.md:784-796`; `docs/CONTENT_COVERAGE.md:169-181` (D-223's 5–7 per occupied tier)
- **Evidence type**: docs
- **Verification limitations**: None material.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — MEDIUM drift: SPEC §5.8.1's 100-per-topic (≈3.4×) stands unmarked against D-223; SPEC-unmarked-departure family with ARCH-25/REQ-35/REQ-37/REQ-43)

#### WORK-32
- **Claim ID**: WORK-32
- **Domain**: known-limitation
- **Intended state**: Three of eleven first-visit disclosures describe behaviour that does not exist — confirm the absence of (a) a challenge route, (b) an image upload path, (c) a tutor/manager read view.
- **Repository-observed state**: All three absent, confirming the finding. (a) No challenge route or endpoint: case-insensitive grep for `challenge` across `apps/learning-api/src`, `apps/learning-web/src`, `apps/chat-api/src` returns two hits only, both difficulty *labels* (`ExamScreen.tsx:65` `4: "Challenge"`, `:66` `5: "Advanced challenge"`). (b) No image upload path: grep for `upload|UploadFile|multipart` returns no route, no handler, no client; the only "image" hits are a Docker trust-store comment (`session_event_relay.py:69`) and `QuestionFigure.tsx:5-7`, which states figures are *data*, not images ("there is no image to fetch, nothing to store"). (c) No tutor/manager-facing view: `apps/learning-web/src/screens/` holds 11 screens — Attendance, BookmarkedResults, ChildSelection, DevLogin, Exam, Intervention, Results, StageTransition, Start, StudentDashboard, TopicSelect — none tutor- or manager-facing. The roles exist server-side and reach report payloads through `report._AUDIENCE_FIELDS["tutor"]` / `["branch_manager"]` (`report.py:202-211`), but the read path is exactly the accepted-risk fall-through in `authorization.py:66-71`.
- **Evidence**: as cited inline above
- **Evidence type**: negative grep + code
- **Verification limitations**: Negative existence over three named surfaces; a feature under a different name would not have matched. `FIRST_VISIT_NOTICE.md:33-35/201-218` was not re-read to confirm the disclosure numbering (§2.11/§2.8/§2.5).
- **Classification**: CONFIRMED_IN_REPOSITORY

#### WORK-33
- **Claim ID**: WORK-33
- **Domain**: open-item
- **Intended state**: A product decision on shipping eight disclosures rather than eleven, owned by frozen S45.
- **Repository-observed state**: **No DECISIONS ruling exists.** A corpus grep for the decision language (`ship eight`, `eight, not eleven`, `eight of the eleven`, `eight disclosures`) returns exactly two non-ledger hits, and **both are recommendations, neither is in DECISIONS.md**: `FIRST_VISIT_NOTICE.md:220` ("**The recommendation is to ship eight, not eleven**, and to attach 2.5, 2.8 and 2.11 to the work...") and `PROGRESS.md:982` ("Recommendation: **ship eight, not eleven**"). DECISIONS.md contains zero occurrences. The blocking statement is intact at `FIRST_VISIT_NOTICE.md:236` ("Counsel review of the resulting text remains a §6.1 launch gate."), and its owner S45 sits inside the D-152-frozen S43–S47 block.
- **Evidence**: `docs/FIRST_VISIT_NOTICE.md:214-218`, `:220`, `:231-237`, `:3-13`; `docs/PROGRESS.md:978-982`; `docs/ROADMAP.md:1500-1507` (S45, frozen), `:1438-1445` (freeze banner); zero-hit DECISIONS grep
- **Evidence type**: docs (negative grep)
- **Verification limitations**: Negative evidence; a ruling phrased without any of the four searched forms would be missed.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — drift **HIGH**: the eight-vs-eleven disclosure decision is unmade, owned by a frozen session, and exists only as a recommendation in a document that disclaims being the Privacy Notice — launch-gate-adjacent for a minors-facing notice)

#### WORK-34
- **Claim ID**: WORK-34
- **Domain**: user-decision
- **Intended state**: OPEN_DECISIONS #1 fixed by D-325 via option A — `flow._templates_to_avoid` exists and excludes the session's exam templates from study selection; `journey-student.spec.ts:377` covers it.
- **Repository-observed state**: Both present. `_templates_to_avoid` exists, unions study templates with the pre-exam session's templates, and is called from both previously-defective on-demand paths. The e2e spec asserts no exam stem is re-served as study. The recorded reasoning matches option A, and the "B is unachievable" argument appears in code as well.
- **Evidence**: `apps/learning-api/src/learning_api/services/flow.py:249-281` — `async def _templates_to_avoid(*, question_repo, assessment_repo, study_items, pre_assessment_session_id) -> set[str]` with docstring "Every template this session has already shown the student — study **and exam** (D-325). ... Measured on the dev database: **57 of 201 study items repeated one of their own session's exam templates**, of which **17 came through these two paths** (11 base, 6 remediation)."; call sites `flow.py:685` and `:823`; option-B-unachievable reasoning at `study_plan.py:19-29`, `:130-144` and `variant_persistence.py:114-116`; `e2e/tests/learning/journey-student.spec.ts:377-384` — `// D-325: no question the exam asked may be re-served as study practice.` then `const repeated = [...studyStems].filter((stem) => examStems.has(stem));`
- **Evidence type**: code + test-source
- **Verification limitations**: Test not executed. `_templates_to_avoid` deliberately does not consult the post-exam (`flow.py:272-273`: "it does not exist yet while study is running, and §5.13.2's pre/post parallel-form rule is `assessment_builder`'s job"), so the exclusion is pre-exam-only by design. The "genuinely open remnant is content" half is not code-verifiable.
- **Classification**: CONFIRMED_IN_REPOSITORY

#### WORK-35
- **Claim ID**: WORK-35
- **Domain**: user-decision
- **Intended state**: OPEN_DECISIONS #4 — the user chose option D, "Consolidate the checkpoint into long-term durable memory according to some criteria, then keep it there", reusing `packages/memory` (S25) which already consolidates and already has a scheduled entrypoint, with design review before code and staging numbers before sizing (ROADMAP U7). Phase 3 must confirm the consolidation job exists next to `retention-purge`.
- **Repository-observed state**: **Yes — a `session-consolidate` job exists in the same Terraform `locals.jobs` map as `retention-purge`, enabled, and ordered first.** `terraform/modules/scheduled-jobs/main.tf:40-61`: `schedule = "cron(0 18 * * ? *)"`, `command = ["python", "-m", "learning_api.services.session_consolidation_cli"]`, `description = "Project completed learning threads into learning_sessions (U7/D-332)."`, `retry_attempts = 2`, `enabled = true`; its comment states the ordering rationale — "**First in the daily order, and the ordering is the point (D-356)** ... That job is deliberately unscheduled today; scheduling it before this one would be actively unsafe, which is why this lands first and alone." `retention-purge` sits at `:74-88` (`cron(50 18 * * ? *)`, `retention_purge_cli`), and the pre-existing memory job at `:89-106` (`cron(30 18 ? * SUN *)`, `["python","-m","intellichoice_memory.consolidate_cli"]`, `retry_attempts = 0`) — so the reuse of `packages/memory`'s already-scheduled entrypoint is real. Schedules are generated, not just declared: `:182-183` `resource "aws_scheduler_schedule" "job" { for_each = local.jobs`, `:198 state = var.enabled && each.value.enabled ? "ENABLED" : "DISABLED"`, and the environment wires it into alarming at `terraform/environments/staging/main.tf:777-782` (`nightly_job_events = ["session-consolidate","chat-purge","retention-purge","memory-consolidate"]`). **Application code, storage and observability all exist**: `session_consolidation_cli.py` (docstring: "**This is the 'extract → store separately' half of the user's design, and it ships before the 'delete' half deliberately.**"), migrations `6538a95bc990_d331_learning_sessions.py` and `4cfc45b7c5ff_d333_memory_consolidated_at.py`, model/repo `learning_session.py`, job constant `JOB_SESSION_CONSOLIDATE`, and four test files. **The "then keep it there" half is honoured by omission**: `checkpoint_retention_cli.py` exists with a manual `Makefile:106` target and its own tests but is **not** in `locals.jobs`, per `docs/ARCHITECTURE.md:31-36` "That retention job stays **unscheduled** until this one has a record of firing." Design review before code is documented at `docs/U7_CHECKPOINT_CONSOLIDATION.md:1-30`.
- **Evidence**: `terraform/modules/scheduled-jobs/main.tf:13-20,40-61,62-73,74-88,89-106,107-126,182-183,198`; `terraform/environments/staging/main.tf:772-782`; `apps/learning-api/src/learning_api/services/session_consolidation_cli.py:1-40`; `apps/learning-api/src/learning_api/services/checkpoint_retention_cli.py:3`; `Makefile:106`; `packages/db/alembic/versions/{6538a95bc990_d331_learning_sessions,4cfc45b7c5ff_d333_memory_consolidated_at}.py`; `packages/observability/src/intellichoice_observability/scheduled_jobs.py`; `docs/U7_CHECKPOINT_CONSOLIDATION.md:1-30`; `docs/ARCHITECTURE.md:26-36`; `docs/OPEN_DECISIONS.md:171-215`
- **Evidence type**: terraform config + code + migration source + test-source (existence)
- **Verification limitations**: Terraform proves the schedule is *declared* ENABLED, not that AWS holds it or that it has fired — the claimed idempotency numbers (36,929 rows, 0 written on a second run, 40 s vs 4m00s) and criterion 6's ≥1-week unattended clock are runtime facts → **3B**. `terraform/environments/staging/terraform.tfvars` was not read (existence only), so the environment-level `youtube_sync_enabled` value is unverified here. No terraform or aws command was run.
- **Classification**: CONFIGURED_NOT_RUNTIME_VERIFIED (the consolidation job exists beside `retention-purge` in config and code; unattended execution is unverified in-repo. Drift LOW: `scheduled-jobs/main.tf:13-20`'s header comment "Four jobs are defined, three are enabled" contradicts its own `locals.jobs` (five defined, four enabled) — the same stale comment recorded under ARCH-04, a comment-only fix inside the operative file.)

#### WORK-37
- **Claim ID**: WORK-37
- **Domain**: deferred-work
- **Intended state**: OPEN_DECISIONS #6 — the video catalog is parked, and the D-326/D-337 guard's current condition is `covered == 0 and deferred == 0`.
- **Repository-observed state**: Confirmed verbatim. `packages/youtube/src/intellichoice_youtube/sync_cli.py:77` — `return covered == 0 and deferred == 0`, in `saw_whole_channel(covered: int, deferred: int) -> bool` (`:58`). The docstring records both the defect and the loss event: "D-326's addendum guarded only on `deferred == 0` while its own comment described the resumability case correctly. On staging 2026-08-15 a run with `covered=72, deferred=0` evaluated this as 'saw everything' and marked **182 videos inactive** - the entire previously-active catalog... Net coverage still rose 72 -> 76 skills, which is precisely why it was easy to miss" (`:66-71`) — matching the claim's 182-row figure exactly. The two independent reasons are enumerated at `:61-65`. The regression test targets the *computation*, not just the effect: `packages/youtube/tests/test_sync_preflight.py:166` — `assert saw_whole_channel(covered=72, deferred=0) is False`, with `:162-164` recording why, and `sync_cli.py:74-76` noting "Tested here rather than only through `sync_channel`, because the existing tests passed this flag *in*". The flag's effect is separately tested at both polarities: `packages/youtube/tests/test_catalog_sync.py:360-369` (False → `videos_marked_inactive == 0`) and `:402-408` (True → `videos_marked_inactive == 1`).
- **Evidence**: `packages/youtube/src/intellichoice_youtube/sync_cli.py:58-77, 80-90`; `packages/youtube/tests/test_sync_preflight.py:28, 162-166`; `packages/youtube/tests/test_catalog_sync.py:356-369, 398-409`; `docs/OPEN_DECISIONS.md:23-28, 32-33`
- **Evidence type**: code + test-source
- **Verification limitations**: The live catalog figures (497 videos, 363 active-and-approved, 102 of 112 skills servable, last synced 2026-08-15 07:39 UTC) are database facts unverifiable from the repository — only the 112-skill denominator is checkable. Whether `YOUTUBE_YOUTUBE_API_KEY` is provisioned is a credentials fact deliberately not inspected. Tests not executed.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — for the guard condition, the 182-row loss event and the regression test. LOW note: `OPEN_DECISIONS.md:32-33` describes #6 as "parked, not blocking" while `PROGRESS.md:105` still lists it as "blocked on the YouTube key" — two documents giving opposite answers about whether #6 blocks launch.)

#### WORK-40
- **Claim ID**: WORK-40
- **Domain**: user-decision
- **Intended state**: Three of OPEN_DECISIONS #10's five sub-items have build consequences — a new API field for the narrative header, the ladder-pause breadcrumb, and the `formatDateLabel` CDT fix.
- **Repository-observed state**: (1) **New API field — BUILT.** `apps/learning-api/src/learning_api/routers/sessions.py` carries `stage_narrative_stage: str | None = None` on five response models (lines 274, 319, 351, 433, 458) alongside `stage_narrative`/`stage_narrative_evidence`. Consumed in `App.tsx` (`snapshot.stage_narrative_stage`) and used in `StageTransitionScreen.tsx:39-45`, whose `EVIDENCE_TITLE` map returns "Why this is your next step" for `pre_intro`/`pre_outro`/`study_step`/`study_outro` and **"What this session showed" for `post_outro`**, with `NEUTRAL_EVIDENCE_TITLE` for unknown/absent stages. (2) **Ladder-pause breadcrumb — BUILT and wired.** `e2e/fixtures/learning-flow.ts:411-433` adds a `note?: (message: string) => void` parameter documented as "Breadcrumb sink (U1, D-324). **Instrument only — this function's behaviour is deliberately unchanged.**"; three specs pass it (`journey-student.spec.ts:236`, `journey-terminal.spec.ts:259`, `journey-bands.spec.ts:130`). (3) **`formatDateLabel` — no symbol of that name exists** anywhere in `apps/learning-web/src` or `apps/chat-web/src`. The nearest is `buildDateLabelFormatter(timeZone)` in `StudentDashboardScreen.tsx:80-82`, bound as `formatOrgDate` at line 427, formatting via `new Date(value).toLocaleDateString("en-US", { timeZone })` using the server-supplied `org_time_zone`; lines 54-60 state the fallback is `UTC` and "deliberately **not** `America/Chicago`". The date-only shift itself is undefended: a date-only string is parsed as UTC midnight and rendered in the org zone, the back-a-day behaviour `OPEN_DECISIONS.md:342` described as "armed".
- **Evidence**: `apps/learning-api/src/learning_api/routers/sessions.py:272-274,317-319,349-351,431-433,456-458`; `apps/learning-web/src/screens/StageTransitionScreen.tsx:25-47`; `e2e/fixtures/learning-flow.ts:411-441`; `e2e/tests/learning/journey-student.spec.ts:236`; `apps/learning-web/src/screens/StudentDashboardScreen.tsx:52-82,219-235,424-427`; `docs/OPEN_DECISIONS.md:336-349`
- **Evidence type**: code + test-source + negative grep (symbol absence)
- **Verification limitations**: It cannot be ruled out that "`formatDateLabel`" is the docs' informal name for `buildDateLabelFormatter`. Whether any endpoint now returns a date-only field — which would arm the bug — was not traced through the API response models.
- **Classification**: PARTIALLY_IMPLEMENTED (adjudicated centrally — items 1-2 built. Item 3 adjudication: `formatDateLabel` names no symbol, but the actual formatter uses the SERVER-SUPPLIED org zone (America/Chicago ⇒ effectively the CDT the decision recorded) with a deliberate UTC fallback per D-324, so the zone policy IS implemented via D-324's design and OPEN_DECISIONS #10's wording simply predates the mechanism. Residual: the date-only back-a-day shift remains unmitigated ("armed"). Drift LOW-MEDIUM: doc wording plus an armed edge case.)

#### WORK-41
- **Claim ID**: WORK-41
- **Domain**: user-decision
- **Intended state**: OPEN_DECISIONS #11 — option B chosen (D-384): security updates installed in the runtime stage of both Dockerfiles.
- **Repository-observed state**: Confirmed in both, identical three-line form in the `runtime` stage: `RUN apt-get update \ && apt-get -y upgrade \ && rm -rf /var/lib/apt/lists/*`. learning-api carries the full rationale (D-384, `util-linux 2.41.5-0+deb13u1`, `CVE-2026-53615`, "Trivy prints `Total: 9` because it counts rows, not CVEs", "no fixed base digest to pin to", and `upgrade` not `dist-upgrade`); chat-api cross-references it ("Identical base image, identical finding, and both scans failed together"). The accepted reproducibility cost is written at the line: "image contents now depend on *when* the build ran, so rebuilding the same commit is no longer byte-identical."
- **Evidence**: `apps/learning-api/Dockerfile:40-64`; `apps/chat-api/Dockerfile:34-41`
- **Evidence type**: code (Dockerfile config)
- **Verification limitations**: Whether the scan gate is currently green is 3B.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — no new drift)

#### WORK-42
- **Claim ID**: WORK-42
- **Domain**: user-decision
- **Intended state**: OPEN_DECISIONS #12 (D-390) — an interstitial rather than an embed; the card stays a real anchor with a real `href`, the click is intercepted, the element is not replaced.
- **Repository-observed state**: Implemented exactly as described. `apps/learning-web/src/screens/InterventionScreen.tsx:373-434` — `VideoContent` holds `const [confirming, setConfirming] = useState(false)`; the card is `<a className="video-card" href={intervention.video_url} target="_blank" rel="noreferrer" onClick={(event) => { event.preventDefault(); setConfirming(true); }}>`, with an adjacent comment: "Still a real anchor with a real `href`, deliberately: middle-click and 'open in new tab' keep working, screen readers still announce a link, and `video-intervention.spec.ts` still reads the href off this element. The click is intercepted rather than the element replaced." The interstitial renders when `confirming`, `role="group"` / `aria-label="Before you open this video"`, plain-language copy naming YouTube as not part of IntelliChoice, and two actions: an `<a>` "Open the video" (same `href`, `target="_blank"`) and a "Stay here" button. No `<iframe>`; the function's docstring records the embed refusal as a privacy decision. The comment at line 405 cites "OPEN_DECISIONS #12, decided 2026-08-17".
- **Evidence**: `apps/learning-web/src/screens/InterventionScreen.tsx:364-434`, and the anchor referenced at `:180`
- **Evidence type**: code
- **Verification limitations**: `e2e/tests/learning/video-intervention.spec.ts` exists but was not executed, so "the existing spec's href assertion still holds" is unverified. The accepted middle-click bypass follows from the anchor being real and is not separately observable statically.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally)

#### WORK-43
- **Claim ID**: WORK-43
- **Domain**: user-decision
- **Intended state**: OPEN_DECISIONS #14 (D-405) — vitest+jsdom configured in each `vite.config.ts`, a `test` script, a `Test` CI step, `src/test/setup.ts` in both, `@testing-library/react` arriving with D-413.
- **Repository-observed state**: All four present and near-identical in both apps. Both `vite.config.ts` files import from `vitest/config` and carry a `test` block with `environment: "jsdom"`, `include: ["src/**/*.test.ts", "src/**/*.test.tsx"]`, `setupFiles: ["./src/test/setup.ts"]`, and the same D-405 rationale comment (jsdom has no `EventSource`, so the stream tests install their own fake). `apps/learning-web/src/test/setup.ts` (1426 bytes) and `apps/chat-web/src/test/setup.ts` (1202 bytes) both exist. `"test": "vitest run"` in both `package.json` files (line 10 each). `.github/workflows/ci.yml`: a `- name: Test` / `run: npm test` step in the `learning-web` job (lines 113-114) and in the `chat-web` job (lines 142-143), each preceded by the same "D-405: added with the first frontend unit tests (OPEN_DECISIONS #14)" comment and placed before `Typecheck + build`. `@testing-library/react ^16.3.2` and `@testing-library/dom ^10.4.1` in **both** `package.json` files (learning-web 23-24, chat-web 20-21).
- **Evidence**: both `vite.config.ts`; both `src/test/setup.ts`; `.github/workflows/ci.yml:96-146`; both `package.json`
- **Evidence type**: code + CI config
- **Verification limitations**: Nothing executed — configuration presence, not that `npm test` passes. The two-vs-four count discrepancy in `docs/OPEN_DECISIONS.md:5-6` is a docs-only arithmetic question and was not reconciled.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — all repository-side elements present)

#### WORK-44
- **Claim ID**: WORK-44
- **Domain**: user-decision
- **Intended state**: OPEN_DECISIONS #2 (client-error sink on both apps with a shared anonymous bucket on chat), #3 (`react-router` decided — decision only, no source read had confirmed a build), #9 (26-PR backlog cleared), #13 (`downloadIcs` DOM contract closed by a Playwright spec).
- **Repository-observed state**: **#2 — both routes exist and are mounted.** `apps/learning-api/src/learning_api/routers/client_errors.py:48` → `APIRouter(prefix="/learning/client-errors", tags=["learning-client-errors"])`, included at `main.py:415`; `apps/chat-api/src/chat_api/routers/client_errors.py:58` → `APIRouter(prefix="/chat/client-errors", ...)`, included at `main.py:317`. The chat router's docstring states the claim's reasoning in shape: "optional token, two buckets, and one of them is shared" — authenticated keyed on `sub` at 20/min, anonymous sharing "a single app-wide bucket" at 60/min, `_ANONYMOUS_BUCKET = "anonymous"` at line 74, and the per-`chat_session_id` alternative rejected as forgeable. Tests exist for both. **#3 — `react-router` is installed and routing in learning-web, and deliberately absent from chat-web.** `apps/learning-web/package.json:19` `"react-router-dom": "^7.18.2"`; `main.tsx:3` imports `BrowserRouter`; `App.tsx:2` imports `useLocation, useNavigate`; `e2e/tests/learning/routing.spec.ts` asserts reload-on-dashboard and Back-button behaviour. chat-web has no router dependency and `apps/chat-web/src/main.tsx:39` states "D-381: this app has exactly one screen and no router". **#13 — closed as described**: `e2e/tests/chat/ics-download-dom-contract.spec.ts` asserts the anchor is appended before `click()` and revoked on a later tick, its docstring naming D-352 → V11/D-392 → W5/D-397 → D-399.
- **Evidence**: the two `client_errors.py` routers and their `main.py` include lines; `apps/chat-api/src/chat_api/routers/client_errors.py:1-77,121-135`; `apps/learning-web/package.json:19`; `apps/learning-web/src/main.tsx:3`; `apps/learning-web/src/App.tsx:2`; `apps/chat-web/src/main.tsx:39`; `e2e/tests/learning/routing.spec.ts`; `e2e/tests/chat/ics-download-dom-contract.spec.ts`
- **Evidence type**: code + test-source + CI/build config (manifests)
- **Verification limitations**: Nothing executed. **#9's "26-PR backlog cleared" is a GitHub-state question that cannot be verified from the working tree** — no `gh` command was run; that half is UNVERIFIED and deferred to 3B/external.
- **Classification**: CONFIRMED_IN_REPOSITORY (adjudicated centrally — for #2/#3/#13, with the #3 scope note that routing is learning-web only, chat-web being routerless by D-381, which is a clarification rather than drift. #9's 26-PR GitHub state → UNVERIFIED, deferred 3B/external.)

---

## 4. Deferred lists

### 4.1 Deferred to Phase 3B (§9 group c) — 14 claims

All 14 group-(c) items are listed with their §9 evidence line. **TEST-15 and TEST-16 were answered
inside 3A** (their instrument is repo-local — see their blocks in §3.5) and are struck from what 3B
owes; the remaining **12** are the live/staging work 3B must do.

| Claim | §9 evidence line | What 3B must do |
|---|---|---|
| **REQ-18** | schema-invalid rate; is capture enabled now | Read the live schema-invalid rate and confirm whether capture is enabled today; the doc figure is aged. |
| **REQ-46** | access-hint recall since D-371 | Re-measure access-hint recall on current staging traffic rather than re-quoting D-371's number. |
| **REQ-50** | SLO instrumentation; 100-concurrent ever demonstrated | Check whether SLO instrumentation exists in the deployed stack and whether 100 concurrent users was ever demonstrated. |
| **SEC-27** | `cost_reservations` rows unverified against staging | Query staging `cost_reservations` and verify the rows the claim assumes. |
| **COST-15** | re-run only if a current baseline needed | Re-run the spend baseline only if 3B needs a current number; otherwise mark aged-by-design. |
| **COST-26** | live SNS subscription state (user-side) | Read live SNS subscription state (including any PendingConfirmation); this is user-side and cannot be inferred from config. |
| **TEST-15** | re-run anchored awk on AUDIT_FINDINGS | **Answered in 3A** — awk returned 0 against the in-repo register. Nothing owed to 3B. |
| **TEST-16** | execute the awk, record actual output | **Answered in 3A** — actual output recorded as 0. Nothing owed to 3B. |
| **TEST-21** | compare current suite counts | Execute the suites and compare current counts against the quoted ones. |
| **TEST-28** | re-run the suites and compare | Execute the suites and compare; 3A never ran a test. |
| **WORK-02** | live SNS subscription state (user-side) | Same live SNS read as COST-26; user-side action. |
| **WORK-05** | re-run counts on current HEAD | Re-run the quoted counts on current HEAD and record what changed. |
| **WORK-23** | re-measure; completed-session deletion job | Re-measure, and check whether a completed-session deletion job now runs. |
| **WORK-29** | validation run and reject threshold measured | Execute a validation run and measure the reject threshold against the recorded one. |

Additional items 3A explicitly handed to 3B from inside an inspected claim (these are *not* extra
queue items; they are named limitations recorded in the blocks above): ARCH-15 (account Free-Tier
status), ARCH-29 (D-419's NAT-in-plan tension — check live NAT count first, and the tfvars question),
SEC-26 (secret rotation history), WORK-44 #9 (the 26-PR GitHub state), WORK-06 (staging image tag and
rollout), WORK-08 (whether D-401/D-406 are actually applied), WORK-13 (behavioural e2e re-measure),
COST-18 (whether structured job lines reach CloudWatch), SEC-23 (LangSmith retention, external).

### 4.2 Deferred by D-152 (§9 group e) — 14 claims

Each needs the production system, which the freeze forbids touching. Listed so they are not mistaken
for Phase 3 work. All 14 carry the disposition `DEFERRED_BY_D152`; none was inspected in 3A.

| Claim | §9 note |
|---|---|
| **INT-05** | B1 reachability, B2 build match — needs the production API. |
| **INT-08** | S43 ingestion-window guard and loud log — the guard does not exist until S43 runs. |
| **INT-09** | The DNS records actually created — org-side action, not observable here. |
| **INT-10** | Real peak-concurrency measurement — needs production traffic. |
| **INT-11** | `SELECT DISTINCT role` plus a role audit — needs the production database. |
| **INT-14** | B2, B4; `pastCalendars` has no pagination — needs the production API. |
| **INT-17** | Live `signups` data; the loud-log guard — needs production data. |
| **INT-18** | How many accounts would be refused — needs the production account set. |
| **INT-20** | B1 reachability; rung-switch trigger — needs the production API. |
| **INT-24** | `SHOW CREATE TABLE` ×5 drift baseline — needs the production schema. |
| **INT-27** | The whole protocol is a verification plan — nothing to verify until integration starts. |
| **INT-30** | `SELECT DISTINCT role` (D1) — needs the production database. |
| **INT-31** | B2 contract match; login latency — needs the production API. |
| **INT-34** | The whole B/C/D measurement set — needs the production system end to end. |

Two further claims carry `DEFERRED_BY_D152` from *inside* §9 group (a), because they are
compliance-by-absence today and were inspected as such: **INT-15** and **INT-32** (blocks in §3.6).

### 4.3 No new evidence required — 27 claims

§9 identified 27 of the 258 ledger claims as already evidence-complete in Phase 2
(`Evidence still required: none`). They are outside the 231-item queue and received no 3A block,
with one exception noted below.

SEC-14, SEC-21, SEC-22, SEC-28, SEC-29, SEC-30, SEC-31, COST-01, COST-07, COST-12, TEST-03, TEST-19,
TEST-24, INT-01, INT-02, INT-03, INT-04, INT-16, INT-21, WORK-10, **WORK-14**, WORK-16, WORK-17,
WORK-25, WORK-36, WORK-38, WORK-39.

**WORK-14** was inspected anyway by W8 (it sits adjacent to the D-342 content-parking claims that
worker held) and therefore has a block in §3.7. It remains evidence-complete for queue-accounting
purposes; the block is additive, not a correction. The other 26 were not read in 3A.

---

## 5. Classification totals

### 5.1 The 201 evidence blocks

| Classification | Claims |
|---|---|
| `CONFIRMED_IN_REPOSITORY` | 116 |
| `PARTIALLY_IMPLEMENTED` | 29 |
| `CONFIGURED_NOT_RUNTIME_VERIFIED` | 26 |
| `DOCUMENTATION_DRIFT` | 21 |
| `TEST_EXISTS_NOT_EXECUTED` | 5 |
| `CONFLICT` | 2 |
| `UNVERIFIED` | 2 |
| `DEFERRED_BY_D152` | 2 |
| `NOT_IMPLEMENTED` | 2 |
| `NOT_APPLICABLE_TO_REPOSITORY` | 1 |
| `IMPLEMENTATION_DRIFT` | 0 |
| **Total blocks** | **206** |

Per-value membership:

- `CONFLICT` (2): COST-06, WORK-12 — both adjudicated centrally.
- `UNVERIFIED` (2): ARCH-15, SEC-26 — both handed to 3B.
- `DEFERRED_BY_D152` (2 inspected): INT-15, INT-32.
- `NOT_IMPLEMENTED` (2): REQ-21, REQ-24 — both correctly so, dispositioned by D-078.
- `NOT_APPLICABLE_TO_REPOSITORY` (1): ARCH-27.
- `TEST_EXISTS_NOT_EXECUTED` (5): REQ-20, REQ-40, TEST-14, TEST-22, TEST-23.
- `DOCUMENTATION_DRIFT` (21): REQ-35, REQ-37, REQ-43, ARCH-06, ARCH-23, ARCH-24, ARCH-26, SEC-03,
  SEC-17, COST-11, TEST-05, TEST-06, TEST-07, TEST-08, INT-07, INT-26, INT-28, WORK-09, WORK-19,
  WORK-22, WORK-24.
- `PARTIALLY_IMPLEMENTED` (29): REQ-10, REQ-17, REQ-19, REQ-27, REQ-28, REQ-29, REQ-32, REQ-39,
  REQ-41, REQ-44, REQ-49, REQ-51, REQ-52, ARCH-01, ARCH-29, ARCH-33, SEC-04, SEC-10, SEC-12, SEC-13,
  SEC-23, COST-10, COST-29, TEST-02, TEST-04, TEST-27, WORK-21, WORK-27, WORK-40.
- `CONFIGURED_NOT_RUNTIME_VERIFIED` (26): ARCH-02, ARCH-03, ARCH-04, ARCH-07, ARCH-08, ARCH-10,
  ARCH-11, ARCH-12, ARCH-13, ARCH-14, ARCH-22, ARCH-28, ARCH-30, ARCH-35, SEC-16, SEC-25, COST-16,
  COST-17, COST-19, COST-23, COST-27, COST-28, TEST-09, WORK-03, WORK-08, WORK-35.
- `CONFIRMED_IN_REPOSITORY` (116): the balance — REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06,
  REQ-07, REQ-08, REQ-09, REQ-11, REQ-12, REQ-13, REQ-14, REQ-15, REQ-16, REQ-22, REQ-23, REQ-25,
  REQ-26, REQ-30, REQ-31, REQ-33, REQ-34, REQ-36, REQ-38, REQ-42, REQ-45, REQ-47, REQ-48, ARCH-05,
  ARCH-09, ARCH-16, ARCH-17, ARCH-18, ARCH-19, ARCH-20, ARCH-21, ARCH-25, ARCH-31, ARCH-32, ARCH-34,
  SEC-01, SEC-02, SEC-05, SEC-06, SEC-07, SEC-08, SEC-09, SEC-11, SEC-15, SEC-18, SEC-19, SEC-20,
  SEC-24, SEC-32, SEC-33, SEC-34, SEC-35, COST-02, COST-03, COST-04, COST-05, COST-08, COST-09,
  COST-13, COST-14, COST-18, COST-20, COST-21, COST-22, COST-24, COST-25, TEST-01, TEST-10,
  TEST-11, TEST-12, TEST-13,
  TEST-15, TEST-16, TEST-17, TEST-18, TEST-20, TEST-25, TEST-26, INT-06, INT-12, INT-13, INT-19,
  INT-22, INT-23, INT-25, INT-29, INT-33, INT-35, WORK-01, WORK-04, WORK-06, WORK-07, WORK-11,
  WORK-13, WORK-14, WORK-15, WORK-18, WORK-20, WORK-26, WORK-28, WORK-30, WORK-31, WORK-32, WORK-33,
  WORK-34, WORK-37, WORK-41, WORK-42, WORK-43, WORK-44.

### 5.2 Reconciliation against the full §9 accounting

| Bucket | Claims |
|---|---|
| §9 items with a 3A classification (§5.1 minus WORK-14) | 205 |
| §9 group (c) still owed to Phase 3B | 12 |
| §9 group (e) `DEFERRED_BY_D152`, not inspected | 14 |
| §9 group (a) not covered in 3A | 0 |
| **§9 verification queue total** | **231** |
| Evidence-complete outside the queue (§4.3) | 27 |
| **Ledger claims total** | **258** |

Arithmetic: 205 + 12 + 14 + 0 = 231; 231 + 27 = 258. Every §9 claim ID appears exactly once across
"inspected", "deferred to 3B" and "deferred by D-152"; with W10's five blocks there is no longer an
uncovered bucket. WORK-14 is the single block belonging to the 27-claim evidence-complete set, which
is why §5.1 totals 206 and §5.2 counts 205 against the queue.

### 5.3 Phase-2 claims weakened or refuted by 3A evidence

Recorded here as an index only; the register entries are the blocks above.

WORK-19 (floors 30/90/180 refute "not designed"), WORK-20 / WORK-21 / WORK-13 (resolved or stale),
REQ-39 (UI wording absent), ARCH-06 (the losing text falsified by config), COST-06 (CONFLICT — a
spend-ledger hole), REQ-43 (nine → TEN reasons), SEC-13 ("last leak closed" does not hold on the
cancel and error paths), COST-21 / COST-22 ("P1s all closed" irreconcilable at config level; COST-22
still open), WORK-09 (now tracked — refuted as CURRENT), WORK-11 (C8 done; the PROGRESS side
refuted), TEST-08 ("same commit" refuted), WORK-27 (`.env.example` mirrors the documented roster),
WORK-28 (the loop IS built — the header refuted), WORK-30 (CONTENT_COVERAGE figures stale), COST-11
(attribution closed by D-400 — the audit file's open state refuted), REQ-41 ("twelve checks"
overcount plus four unimplemented bullets), ARCH-33 (the Vite-hash "standing control" refuted),
TEST-25 (still-open list → specs exist, already anticipated), SEC-20 / TEST-10 (the ledger's "§6.1
track not started" temporal notes are superseded by `docs/FIRST_VISIT_NOTICE.md`, shipped
2026-08-15), TEST-04 (TRACEABILITY:623's "31 `extra="forbid"` models" refuted — now 41 in non-test
source).
