# LOCAL_EXECUTION_EVIDENCE.md — Phase 3A.5 local executable verification

**Date:** 2026-08-19
**Phase:** 3A.5 (local executable verification), between 3A (static repository read) and 3B (live/deployed).

**Purpose.** Phase 3A classified 206 claims by *reading* the repository. A large share of the
residual uncertainty was not about what the repository says but about whether the repository's own
declared checks actually pass. This phase reduces that uncertainty with safe, local, **executed**
evidence: pytest against the local Docker Postgres and the dev fakes, `make lint`/`make typecheck`,
the two frontend test suites and builds, an Alembic replay from an empty database, and a set of
static verification greps re-run verbatim. Nothing here touches live infrastructure.

**Environment.** Local Docker Compose Postgres (and the MySQL dev fixture), dev fakes for auth /
Bedrock / Gmail / Maps / Calendar / blob storage. pytest 9.1.1; `pytest-timeout` not installed, so
every pytest invocation used `-q -rA` only. Node modules already present in `apps/learning-web`,
`apps/chat-web`, `e2e` (no `npm install`/`npm ci` run). Repo at branch `main`, HEAD `344f016`.
**No AWS credentials were used, no paid API was called, no Playwright run was performed, no
terraform command was run, and no `.env`/`*.tfvars`/credential file was read.** `git status
--porcelain` showed only the pre-existing `?? docs/reconciliation/` before, during, and after.

**Honesty rules used when reading these results.**

1. **Zero-collected is not a pass.** A pytest run that collects 0 tests is recorded as *not
   evidence* and must be recovered before any claim rests on it. Two runs hit this (see §1) and both
   were recovered; the failed instrument is recorded rather than deleted.
2. **A skip is not a pass.** Skips are counted separately and reported; the totals below carry
   0 skips.
3. **Config is not deployed.** Every terraform-, Dockerfile-, and workflow-derived result here is
   *file state*. The repository's own comment at `terraform/environments/staging/main.tf:543-549`
   records a config change that "was never applied … live stayed at the module default the whole
   time", and `terraform apply` is not part of `deploy-staging.yml`. Phase 3B must not assume
   config == live.
4. **Execution cannot confirm an absence.** A passing test proves the implemented path works; a
   zero-hit grep proves the repository does not contain the string searched, in the scope searched.
   Neither proves a requirement is met at runtime.
5. **A passing assertion can be vacuous.** Where the assertion iterates a set that excludes the
   interesting cases, the pass is weak evidence by construction and is labelled as such
   (REQ-44 below).

---

## 1. Execution inventory

### 1.1 pytest invocations (X1)

Working directory for every command: the repository root.

| # | Batch | Scope | Collected | Passed | Failed | Skipped |
|---|---|---|---|---|---|---|
| 1 | 1 | 13 cited files: `test_schema_purity` `test_bedrock_payload_pii_floor` `test_tracing` `test_exam_policy` `test_mastery_bootstrap` `test_report` `test_exam_flow_determinism` `test_rag_search` `test_role_access` `test_learning_graph_routes` `test_calendar_action` `test_admin_escalation` `test_auth_and_attendance` | 183 | 183 | 0 | 0 |
| 2 | 2 | `test_alarm_severity_routing` `test_langsmith_config` `test_request_logging` `test_background_task_trace_join` | 17 | 17 | 0 | 0 |
| 3 | 3a-i | 2 node ids in `test_authored_pipeline.py` (spend reconciliation + duplicate-id settlement) | 2 | 2 | 0 | 0 |
| 4 | 3a-ii | `test_authored_pipeline.py -k "solver"` | 90 collected / 10 selected (80 deselected) | 10 | 0 | 0 |
| 5 | 3b | `test_leak_sample.py` `test_mock_hint_is_leak_clean.py` | 5 | 5 | 0 | 0 |
| 6 | 3c-i | `packages/knowledge/tests/test_retrieval.py` | 22 | 22 | 0 | 0 |
| 7 | 3c-ii | `packages/knowledge/tests/ -k "quote_floor"` | **0 (40 deselected) — exit 5, NOT evidence** | — | — | — |
| 8 | 3c-iii | `apps/chat-api/tests/test_qa_service.py` (recovery for #7) | 23 | 23 | 0 | 0 |
| 9 | 3d | `test_error_detail_contract.py` × 2 apps | 6 | 6 | 0 | 0 |
| 10 | 3e | `test_learning_flow.py::test_attendance_ask_branch_manager_end_to_end` | 1 | 1 | 0 | 0 |
| 11 | 4 | `test_bedrock_gateway.py` `test_cost_reservation.py` `test_cost_reservation_estimates.py` | 44 | 44 | 0 | 0 |
| 12 | 5 | `test_study_plan_difficulty_routing.py` `test_sync_preflight.py` `test_catalog_sync.py` + `test_authored_bank.py::test_editing_an_item_already_in_the_database_propagates` | 41 | 41 | 0 | 0 |
| 13 | 6 | `test_checkpoint_retention.py` `test_session_consolidation.py` `test_consolidation_scheduler.py` `packages/memory/tests/test_consolidation.py` | 55 | 55 | 0 | 0 |
| 14 | 7-i | `test_stream_and_history.py -k "token or staging"` | 25 collected / 16 selected (9 deselected) | 16 | 0 | 0 |
| 15 | 7-ii | `test_learning_chat.py -k "safety"` | **0 (11 deselected) — exit 5, NOT evidence** | — | — | — |
| 16 | 7-iii | `test_learning_chat.py` whole file (recovery for #15) | 11 | 11 | 0 | 0 |
| 17 | 7-iv | `test_turn_reasons.py` `test_branch_locator.py` `test_client_errors.py` × 2 apps | 43 | 43 | 0 | 0 |
| 18 | 8 | `packages/db/tests/` | 83 | 83 | 0 | 0 |
| 19 | 8b | `test_autogenerate_never_drops_the_checkpoint_tables.py` alone (confirmation re-run) | 4 | 4 | 0 | 0 |

**Recorded total: 562 unique tests executed (566 test executions), 0 failed / 0 skipped / 0 errors**,
across 16 targeted invocations. Two zero-collection runs, both recovered and both kept on the
record. Environmental recovery (`uv sync --all-packages`) was never needed.

*Reproducibility note (discrepancy resolved):* X1's `TOTALS` line wrote 583 while its own addends
(183+17+2+10+5+22+23+6+1+44+41+55+16+11+43+83+4) sum to 566 — an addition error. The remaining
4-test difference is a **double count**: row 19 is a confirmation **re-run** of
`test_autogenerate_never_drops_the_checkpoint_tables.py`, whose 4 tests are already inside row 18's
83-test `packages/db/tests/` run. Hence **562 unique tests, 566 executions**. Every per-invocation
number above was verified against the raw log and is correct as tabulated.

### 1.2 Lint, typecheck, frontend, migration (X2 + X1 batch 8)

| Command | Result |
|---|---|
| `make lint` (`ruff check .` then `ruff format --check .`) | exit 0 — `All checks passed!` / `440 files already formatted`; read-only, no file rewritten |
| `make typecheck` (`uv run pyright`) | exit 0 — `0 errors, 0 warnings, 0 informations` |
| `make e2e-typecheck` (`cd e2e && npx tsc --noEmit`) | exit 0 — clean; only output is an unrelated node `ExperimentalWarning` |
| `apps/learning-web` `npm test` (`vitest run`) | exit 0 — `Test Files 4 passed (4)` / `Tests 26 passed (26)` / `Duration 1.39s` |
| `apps/learning-web` `npm run build` (`tsc -b && vite build`) | exit 0 — `644 modules transformed`, `built in 295ms`, `index-l54-gT7N.js 700.04 kB │ gzip: 206.97 kB`, one `(!) Some chunks are larger than 500 kB` warning |
| `apps/chat-web` `npx vitest run` | exit 0 — `Test Files 5 passed (5)` / `Tests 49 passed (49)` |
| `apps/chat-web` `npm run build` | exit 0 — `39 modules transformed`, `built in 185ms`, `index-DhP_AL5K.js 220.27 kB │ gzip: 68.85 kB` |
| Migration replay from empty | scratch DB `reconciliation_3a5_scratch` created → `alembic upgrade head` exit 0, **37 migrations applied base → head** (`9e6877432c14` initial domain schema … → `8509c0486d8d` d421 chat escalation sends) → `alembic current` = `8509c0486d8d (head)`, `alembic heads` = `8509c0486d8d (head)` (**single head, no branch divergence**) → scratch DB dropped and confirmed absent from `\l`. No repo file touched. |
| Static verification greps | **~20** static verification greps across X2's 25 steps (plus supporting `ls`/`find`/AST reads) |
| AST field count | `LearningState`: **32** annotated fields; `QAState`: **27** annotated fields |

**Frontend total: 75 tests (26 learning-web + 49 chat-web), 0 failed / 0 skipped.**
**Grand total across both lanes: 562 unique pytest (566 executions) + 75 frontend = 637 unique tests, zero failures and
zero skips anywhere.** Build artefacts landed only in the gitignored `dist/`.

---

## 2. Per-claim records

Vocabulary: **LOCALLY_VERIFIED** = executed local evidence now confirms the *repository-side half*
of the claim. It refines rather than replaces the 3A classification. Runtime / live / deployed halves
keep their Phase 3B deferral in every case.

### 2.1 REQ family

#### REQ-10
- **Claim ID**: REQ-10 — five interrupt classes exist, not SPEC's six; no image-analysis interrupt, no sensitivity-keyed email gate.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest apps/learning-api/tests/test_learning_graph_routes.py apps/chat-api/tests/test_calendar_action.py apps/chat-api/tests/test_admin_escalation.py …` — same run as TEST-02, batch 1.
- **Why relevant**: Converts "the five interrupt-class test files exist" into "the five interrupt classes behave".
- **Result**: exit 0, part of `183 passed in 18.90s` (collected 183 / passed 183 / failed 0 / skipped 0).
- **What it proves**: The five implemented interrupt classes are exercised and pass locally against the dev fakes.
- **What it does NOT prove**: The "six vs five" question is a SPEC-reading item no command settles; `analyze_image` has no feature to gate (dispositioned by D-078), and the absent sensitivity-keyed email gate cannot be confirmed absent by execution.
- **Revised evidence classification**: unchanged — evidence strengthened.

#### REQ-12
- **Claim ID**: REQ-12 — unknown attendance is not treated as present (non-negotiable rule 5, fail closed).
- **Previous Phase 3A classification**: CONFIRMED (cited test unexecuted)
- **Command executed**: `uv run pytest apps/learning-api/tests/test_auth_and_attendance.py …` — same run as TEST-02, batch 1.
- **Why relevant**: `AttendanceStatus.UNKNOWN` is a *routine* production path per D-152 §2, so the fail-closed assertion is load-bearing, not an edge case.
- **Result**: exit 0, inside `183 passed` (0 failed / 0 skipped).
- **What it proves**: `test_unknown_attendance_is_not_treated_as_present` executes and passes; the gate fails closed in code.
- **What it does NOT prove**: That production's `signups.attended = null` maps to `UNKNOWN` through the real `ProfileAdapter` — integration is deferred (D-152), so the mapping is dev-fake-verified only.
- **Revised evidence classification**: unchanged — evidence strengthened.

#### REQ-17
- **Claim ID**: REQ-17 — 11 of 13 structured-output artifact types have a model plus a production call site; topic mapping and email draft do not.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -rn "TOPIC_MAPPING" packages apps --include="*.py"`; `grep -rn "TOPIC_MAPPING\|topic_mapping" apps packages --include="*.py"`; `grep -rln "generate_structured" apps/learning-api/src apps/chat-api/src packages --include="*.py"`
- **Why relevant**: The 3A block rests entirely on a negative grep, so re-running it verbatim is the whole test of the claim's wording.
- **Result**: **1 match, not zero** — `packages/shared/src/intellichoice_shared/bedrock.py:37: TOPIC_MAPPING = "topic_mapping"`. Caller sweep: only that line plus an unrelated filename string at `packages/curriculum/src/intellichoice_curriculum/content.py:270`. `generate_structured` appears in 29 files (12 source call sites, 1 gateway, 1 schema module, 15 tests) — none of them references the slot.
- **What it proves**: The enum slot exists and has **zero callers**; no payload model and no response model downstream of it. The `BedrockTask` class docstring itself concedes the reservation ("named now so the model registry's keys are stable … not because logic exists for them yet").
- **What it does NOT prove**: Whether the two missing artifact types *should* exist is a SPEC-scope judgement; and the email-draft half was not re-swept here.
- **Revised evidence classification**: unchanged — **3A wording corrected (LOW)**: "TOPIC_MAPPING absent" is wrong as stated; the correct wording is "**declared, never used**".

#### REQ-19
- **Claim ID**: REQ-19 — gateway has timeout / retry / output ceiling / session budget / circuit breaker / `worst_case_cost_cents`; guardrails absent repo-wide; gateway-level PII redaction absent (lives at callers).
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest packages/adapters/tests/test_bedrock_gateway.py packages/db/tests/test_cost_reservation.py apps/learning-api/tests/test_cost_reservation_estimates.py -q -rA` (batch 4).
- **Why relevant**: Rule 7 — all paid calls through the gateway with timeouts, bounded retries, max-token limits and cost accounting. This is the direct test of the six named features.
- **Result**: exit 0, 3.2s — collected 44 / passed 44 / failed 0 / skipped 0 / errors 0. (Expected `bedrock_call_failed` WARNING lines are the tests' own injected failures.)
- **What it proves**: All six cost-and-safety features of the gateway execute and pass locally, including the reservation path in `packages/db` and the app-level estimate path.
- **What it does NOT prove**: "No paid call bypasses the gateway" — no test enumerates call sites. An out-of-band AWS-console Bedrock guardrail is a live-AWS fact (3B). Gateway-level PII redaction remains absent, and execution cannot confirm an absence.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (repo half)** for the six gateway features; the guardrails / DLQ / smaller-model absences were re-confirmed by zero-hit greps (see REQ-49).

#### REQ-20
- **Claim ID**: REQ-20 — the spend-reconciliation test and measurement script exist and pass; `skipped_duplicate_id` gap open; 31% vs 32.0% numeric inconsistency across code and docs.
- **Previous Phase 3A classification**: **TEST_EXISTS_NOT_EXECUTED**
- **Command executed**: `uv run pytest "packages/curriculum/tests/test_authored_pipeline.py::test_a_slots_rows_account_for_every_cent_the_slot_reports" "packages/curriculum/tests/test_authored_pipeline.py::test_per_candidate_settlement_survives_a_duplicate_id" -q -rA` (batch 3a).
- **Why relevant**: The claim's own words are "exist **and pass**"; only execution can supply the second verb.
- **Result**: exit 0, 2.5s — collected 2 / passed 2 / failed 0 / skipped 0 / errors 0.
- **What it proves**: Both cited tests pass against the local Postgres — every cent the slot reports is accounted for by its rows.
- **What it does NOT prove**: Nothing about a *paid* reconciliation run (`scripts/measure_spend_reconciliation.py` was not invoked against real spend). The 31% vs 32.0% inconsistency is documentary and untouched by execution.
- **Revised evidence classification**: TEST_EXISTS_NOT_EXECUTED → **LOCALLY_VERIFIED (repo half)** — both cited tests passed.

#### REQ-27
- **Claim ID**: REQ-27 — `TokenClaims` carries exactly ten claims; `parental_consent_verified` read at four app sites; the gate fails closed via an empty `AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT`; **no student-facing consent notice in either web app**.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -rniE "parental|consent|under 13|guardian" apps/learning-web/src apps/chat-web/src`; `grep -rn "parental_consent" apps packages --include="*.py"`; `grep -rniE "parental consent|COPPA|guardian consent" docs/SPEC.md`
- **Why relevant**: SPEC.md:96 has three sentences; the backend gate discharges sentence 2 and the missing UI notice is sentence 3, so the two halves need separating by evidence.
- **Result**: 23 frontend matches, **all in chat-web and all location-consent** (the `LocationConsentModal`, the `location_consent` interrupt type, comments); **zero matches in `apps/learning-web/src`** for all four patterns. Backend: `packages/shared/src/intellichoice_shared/auth.py:31` declares the field, `:106` refuses a non-exempt student without it, with tests at `apps/learning-api/tests/test_auth_and_attendance.py:178,182` and `apps/chat-api/tests/test_auth.py:181`.
- **What it proves**: The backend gate exists and is tested. The COPPA student-facing notice is absent from both frontends, and the 23 chat-web hits are a *different* consent (SPEC §5.1.4 external action) that does not discharge it — learning-web, the app SPEC.md:96 names, has zero hits.
- **What it does NOT prove**: The fail-closed behaviour of the **empty frozenset** is still unexecuted — no test in the repo pins it, and authoring one is out of audit scope. "Should a notice exist here or upstream in `go.intellichoice.org`" remains a product judgement.
- **Revised evidence classification**: **SPLIT** — the no-parental-notice half → **LOCALLY_VERIFIED (repo half)**; the fail-closed empty-frozenset code half remains **unexecuted** (no test exists).

#### REQ-28
- **Claim ID**: REQ-28 — location-consent copy verbatim and pre-collection; coordinates never in `QAState`; MCP audit rows store no arguments. Two LOW drifts (UI offers ZIP/city but not address; stale `QAState` docstring).
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest apps/chat-api/tests/test_turn_reasons.py apps/chat-api/tests/test_branch_locator.py apps/chat-api/tests/test_client_errors.py apps/learning-api/tests/test_client_errors.py -q -rA` (batch 7-iv); plus `grep -n "ephemeral_location" apps/chat-api/src/chat_api/graph/state.py`.
- **Why relevant**: The 3A block cited no test at all; `test_branch_locator.py` is the suite that actually exercises the consent-then-locate path.
- **Result**: exit 0, 8.2s — collected 43 / passed 43 / failed 0 / skipped 0. `ephemeral_location` grep: **1 hit, a stale docstring at `state.py:4`, not a field**.
- **What it proves**: The branch-locator path executes and passes, and `QAState` genuinely carries no coordinate field — the no-PII-in-graph-state property holds in code.
- **What it does NOT prove**: LangSmith span attributes are external SaaS (never verifiable from the repo). The copy-vs-SPEC comparison and the two LOW drifts stay a reading item; the ZIP/city-but-not-address drift is a UI-audit item.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (code half)** — branch-locator suite passed; trace-payload half stays 3B/external.

#### REQ-32
- **Claim ID**: REQ-32 — `HintResponse.answer_revealed` set by the deterministic fallback; Bedrock Guardrails absent; self-harm/abuse routing is a fixed 10-keyword screen on learning-api only, with no approved safety policy and no escalation destination beyond a boolean flag.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest apps/learning-api/tests/test_learning_chat.py -k "safety" -q -rA` → **exit 5, collected 0 (11 deselected) — NOT evidence**. Recovered with `uv run pytest apps/learning-api/tests/test_learning_chat.py -q -rA`.
- **Why relevant**: The safety screen is the only child-safety mechanism in either app; whether it works is not a documentation question.
- **Result**: recovery run exit 0, 24.2s — collected 11 / passed 11 / failed 0 / skipped 0. The REQ-32 test is `test_self_harm_keyword_short_circuits_to_a_fixed_response_and_flags_for_review` (`apps/learning-api/tests/test_learning_chat.py:474`) — executed, passed.
- **What it proves**: The keyword screen short-circuits to a fixed response and raises the review flag, as claimed.
- **What it does NOT prove**: **The thinness is the finding: exactly ONE test repo-wide guards the self-harm screen** (a grep over `apps/` and `packages/` for `safety_screen|crisis|self_harm|safety_flag` hit this one file only). One test cannot cover a 10-keyword screen's misses, and it says nothing about chat-api, which has no screen at all. Guardrails absence is repo-scoped only — a console-attached guardrail is 3B. "Should chat-api carry a safety screen" is a product judgement.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (single-test, thin)** — the one existing test passed; coverage depth is itself a finding.

#### REQ-39
- **Claim ID**: REQ-39 — bootstrap weights exact (1.0/1.4/1.9/2.5/3.2), no IRT path anywhere; SPEC's "Current estimated level" UI wording appears in neither frontend and no disposition exists.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -rniE "current estimated level" apps/learning-web/src apps/chat-web/src`; `grep -rniE "estimated" apps/learning-web/src apps/chat-web/src`; `grep -rniE "current estimated level|estimated level" docs/SPEC.md`; plus `apps/learning-api/tests/test_mastery_bootstrap.py` in batch 1.
- **Why relevant**: A UI-wording claim is exactly the kind that a broader grep can overturn, so the absence was re-tested at the loosest plausible pattern.
- **Result**: both frontend greps **exit 1 → no matches** — the substring `estimated` does not occur anywhere in either frontend's source, in any case. SPEC prescribes the label twice (`docs/SPEC.md:1111`, `:1451`). What ships instead: `Level {difficulty}` (`ExamScreen.tsx:71`) and `Hint {level} of {max}` (`InterventionScreen.tsx:262`). Weights tests passed inside batch 1's `183 passed`.
- **What it proves**: The absence is now exhaustive at the string level, and the weights are executed-verified.
- **What it does NOT prove**: That the hedging *intent* is unmet — D-409's mastery bands in `ReportView` partly serve it. No command supplies the missing disposition.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (repo half)**; the **MEDIUM UI-wording drift STANDS**.

#### REQ-40
- **Claim ID**: REQ-40 — the two named leak tests assert leak-cleanliness (golden sweep + D-079 negative-integer regression; mock hint introduces no answer).
- **Previous Phase 3A classification**: **TEST_EXISTS_NOT_EXECUTED**
- **Command executed**: `uv run pytest packages/evals/tests/test_leak_sample.py packages/curriculum/tests/test_mock_hint_is_leak_clean.py -q -rA` (batch 3b).
- **Why relevant**: A leak sweep that has never been run is an assertion about a set, not evidence about the set.
- **Result**: exit 0, 7.4s — collected 5 / passed 5 / failed 0 / skipped 0 / errors 0.
- **What it proves**: `sweep_for_unexpected_leaks() == []` holds on the current golden set, the D-079 negative-integer case is present, and the mock hint introduces no answer.
- **What it does NOT prove**: Leak-cleanliness of *generated* content from a paid run (no generation was invoked), nor of any content added after this commit.
- **Revised evidence classification**: TEST_EXISTS_NOT_EXECUTED → **LOCALLY_VERIFIED (repo half)** — 5/5 leak tests passed.

#### REQ-44
- **Claim ID**: REQ-44 — the no-reason-code-restated sweep iterates a set, but the set is only `REASON_MESSAGES` (5 entries); `UNAVAILABLE_INTENT_MESSAGES`, `LOCATION_*`, `RATE_LIMITED_MESSAGE` and calendar copy are unswept.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest apps/chat-api/tests/test_turn_reasons.py …` (batch 7-iv, same run as REQ-28 / SEC-12 / COST-17).
- **Why relevant**: The assertion is a plain substring check, so it passes *vacuously* for any copy defined outside the dict — the pass and the gap have to be reported together.
- **Result**: exit 0, part of collected 43 / passed 43 / failed 0 / skipped 0.
- **What it proves**: For the copy that *is* in `REASON_MESSAGES`, no reason code is restated to the user.
- **What it does NOT prove**: **The vacuity caveat stands and is the point: the sweep iterates only `REASON_MESSAGES` — 5 of 10 reasons — so a pass is weak evidence by construction.** `UNAVAILABLE_INTENT_MESSAGES`, the `LOCATION_*` strings, `RATE_LIMITED_MESSAGE` and calendar copy are never visited by the assertion; a reason code leaking through any of them would still pass this test.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (weak — vacuity caveat)**; the coverage gap is unchanged.

#### REQ-49
- **Claim ID**: REQ-49 — 4 of §5.29's 19 failure rows sampled. Static concept-hint fallback PRESENT; non-blocking telemetry PRESENT; dead-letter queue ABSENT; smaller-model fallback ABSENT (timeout retries the same `model_id`, then opens the breaker).
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest packages/observability/tests/test_alarm_severity_routing.py …` (batch 2); `grep -rniE "dead.?letter|DLQ" packages apps terraform --include="*.py" --include="*.tf"`; `grep -rniE "fallback_model|smaller.model" packages apps --include="*.py"`.
- **Why relevant**: The alarm-routing test parses the real terraform files, so it runs fully locally and is the only mechanical check on the `langsmith_ingest_failed` route.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0. Both greps **exit 1 → no matches**. What exists instead: `terraform/modules/scheduled-jobs/main.tf:57,70,85,100,111` `retry_attempts = 2/2/2/0/2` with `retry_policy { maximum_retry_attempts = each.value.retry_attempts }` at `:229-230`.
- **What it proves**: The routing half executes and passes. Both absences are re-confirmed at zero hits: no DLQ and no `aws_sqs_*` anywhere, so a scheduled invocation that exhausts 2 retries is simply lost with nothing to replay from; degradation is binary — circuit opens, caller takes its deterministic fallback, no cheaper-model rung.
- **What it does NOT prove**: 15 of 19 §5.29 rows were never sampled in 3A and are not sampled here. A zero-hit grep is scope-bounded, not proof of design intent.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (routing half, config-parsing)**; the two absences re-confirmed; the 15 unsampled rows unchanged.

#### REQ-51
- **Claim ID**: REQ-51 — two substantive mismatches against §5.5.2's 16 node types: Topic Resolver declared "Structured LLM" but deterministic; Tutor Summary Generator declared "Structured service" but produced by the LLM report path; Assessment Manager has no subgraph.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -rn "generate_structured" apps/learning-api/src/learning_api/services/topic_resolver.py`; `grep -nE "^(from|import)|^def |^class |^async def " apps/learning-api/src/learning_api/services/topic_resolver.py`
- **Why relevant**: The deterministic-vs-LLM half is decidable by grep; the vocabulary half is not.
- **Result**: `generate_structured` grep **exit 1 → no matches**. Every import is a DB repository/model or a deterministic policy constant (`WEAK_SKILL_THRESHOLD`); the only `intellichoice_shared.bedrock` import is the `TutorContext` dataclass it *fills in* for a later caller.
- **What it proves**: `topic_resolver.py` makes zero LLM calls — topic resolution is deterministic by construction, consistent with the §5.0 deterministic-core rule, and it explains why REQ-17's `TOPIC_MAPPING` slot has no caller.
- **What it does NOT prove**: The finding turns on undefined SPEC vocabulary ("Structured service", "Tool agent", "Subgraph"); no command resolves that, and the Tutor Summary Generator / Assessment Manager halves were not re-tested here.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (repo half)** — confirmed as claimed by executed grep.

#### REQ-52
- **Claim ID**: REQ-52 — `LearningState` has 32 top-level fields (not SPEC's ~40, not U7's 31); `QAState` has no `ephemeral_location` at all; LangGraph checkpoint tables are not ORM models, so `test_schema_purity.py` does not cover checkpointed state.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run python -c "<ast walk over apps/learning-api/src/learning_api/graph/state.py>"` (and the same over `apps/chat-api/src/chat_api/graph/state.py`); `grep -rn "ephemeral_location" apps packages docs --include="*.py" --include="*.md"`; `packages/db/tests/test_schema_purity.py` in batch 1.
- **Why relevant**: A field count asserted in prose is exactly the kind of number an AST parse settles without judgement.
- **Result**: **`LearningState`: 32 annotated fields — matches the claimed 32 exactly** (`LearningState` is the only class in the file); `QAState`: 27 annotated fields, **no `ephemeral_location`** — the single grep hit is a stale docstring at `apps/chat-api/src/chat_api/graph/state.py:4` claiming the field is "still not present - S15 adds them". `test_no_model_has_a_pii_column_name` passed in batch 1.
- **What it proves**: The count is exact; neither state model carries a name-, email-, or coordinate-shaped field (all identity is `*_external_id`), so §5.4/§5.30 holds in both graphs. `SPEC.md:1942` and that docstring are both documentation drift against correct code.
- **What it does NOT prove**: The named limitation stands — `test_schema_purity.py` walks `Base.registry.mappers`, so **checkpointed state is outside its reach** and no command in this phase closes that.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (repo half)** — 32-field count confirmed by AST parse; no `ephemeral_location` in `QAState` confirmed.

### 2.2 ARCH family

#### ARCH-01
- **Claim ID**: ARCH-01 — `ARCHITECTURE.md`'s declared scope (S0–S34 + S36–S43) is stale in the "up to" direction and session-provenance tagging is missing for the range it claims to cover; `FINAL_ARCHITECTURE.md:3-12` still says "through S31".
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -oE "\(S[0-9]+\)" docs/ARCHITECTURE.md | sort -u`; `grep -cE "D-4[0-9][0-9]" docs/ARCHITECTURE.md`; `grep -noE "D-4[0-9][0-9]" docs/ARCHITECTURE.md`; `grep -nE "^#+ .*D-42[0-9]" docs/DECISIONS.md`
- **Why relevant**: "Stale" has two independent meanings here — decisions cited and sessions tagged — and only one of them turns out to be true.
- **Result**: tags exist for **32 of 48** sessions; **numerically absent: S23, S30, S31, S32, S33, S35, S36, S38, S40–S47 (16 sessions)**. `D-4xx` appears on 10 lines / 11 occurrences (line 2071 carries two), including **D-423** — which is the newest entry in `DECISIONS.md` (`28714: ## D-423 …`). The header at lines 3-13 promises "Session provenance is tagged in each node (e.g. `(S6)`)".
- **What it proves**: **Split verdict.** Decision currency is FINE — the document cites the newest decision that exists. Session provenance is genuinely stale: the `(Sn)` convention was abandoned around S39 while the header still advertises it, and the only tag past S39 is the aspirational `(S48)` used for the *unbuilt* production environment.
- **What it does NOT prove**: Whether the untagged nodes are *wrong*, only untagged. `FINAL_ARCHITECTURE.md`'s "through S31" line was not re-tested here.
- **Revised evidence classification**: unchanged — **3A wording corrected (LOW)**: the accurate finding is the provenance gap (16 of 48 untagged), not a decision-currency gap.

#### ARCH-02
- **Claim ID**: ARCH-02 — `terraform/environments/` contains `staging/` only; no production env; no `aws_organizations_*`.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `ls terraform/environments/`; `grep -rn "aws_organizations" terraform/`; `grep -rn -A6 'backend "s3"' terraform/environments/staging/*.tf`; `grep -rn "allowed_account_ids\|assume_role" terraform/`
- **Why relevant**: Account separation is the boundary that makes a staging mistake survivable; its absence is a config fact, checkable locally.
- **Result**: `ls` → `staging` only. `aws_organizations` → **exit 1, no matches**. State backend: `bucket = "intellichoice-terraform-state-320503430250"`, `key = "staging/terraform.tfstate"`. `allowed_account_ids` appears only as a `null` inside the provider cache (`.terraform/terraform.tfstate`), not in config.
- **What it proves**: Exactly one environment directory and zero Organizations resources — no prod account, no account separation, no organizational guardrail. Two consequences: the state bucket embeds the single account id, so a future prod would be a second key in the *same* bucket unless changed deliberately; and the `aws` provider sets **no `allowed_account_ids`**, so nothing in config prevents an apply landing in whatever account the ambient credentials point at.
- **What it does NOT prove**: Whether a prod AWS account exists outside this repo (live AWS → 3B).
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (config half)** — confirmed as claimed by executed greps.

#### ARCH-03
- **Claim ID**: ARCH-03 — `/dev/token` is the only token-issuing route; no auth provider anywhere (the only OIDC hit is the GitHub Actions deploy provider).
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `grep -riE "cognito|oidc|oauth|saml|auth0|okta|clerk|firebase_auth" apps/learning-api/src apps/chat-api/src packages --include="*.py" -rn | grep -v test`; `grep -rnE "cognito|oidc|oauth" terraform/`; plus SEC-25's gate tests (batch 7-i).
- **Why relevant**: The 3A block says the absence-of-auth half is repo-provable by exhaustive negative grep, so the grep *is* the evidence.
- **Result**: Python — **3 matches, none an identity provider**: a log-redaction key (`logging_config.py:94 "oauth_token"`) and two docstrings (`logging_config.py:11`, `fake_calendar.py:9`). Terraform — every hit is **GitHub Actions OIDC for the deploy role** (`staging/main.tf:294 create_github_oidc_provider = true`, plus `modules/iam/*`). `cognito`, `saml`, `auth0`, `okta`, `clerk` → **zero matches anywhere**.
- **What it proves**: There is no external identity provider in the system. Auth is entirely the project's own JWT verification against the `go.intellichoice.org` token contract; the only OIDC is the CI→AWS deploy-plane trust relationship.
- **What it does NOT prove**: That the *deployed* apps no longer issue dev tokens on the live ALB — that is 3B. No secret value was read.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (repo half)** — zero auth providers confirmed by exhaustive grep; gate logic verified under SEC-25; live ALB reachability remains 3B.

#### ARCH-08
- **Claim ID**: ARCH-08 — two Fargate services, RDS Postgres 16.4, RDS MySQL 8.4.10 fixture, Terraform IaC, env separation by `name_prefix` + single VPC; pgvector is at the migration layer, not the parameter group.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: scratch DB created via `docker exec intellichoice-postgres-1 psql … -c "CREATE DATABASE reconciliation_3a5_scratch;"`; then `cd packages/db && DATABASE_URL="postgresql+asyncpg://…/reconciliation_3a5_scratch" uv run alembic upgrade head`; `alembic current`; `alembic heads`; `DROP DATABASE`; then `uv run pytest packages/db/tests/ -q -rA`.
- **Why relevant**: The pgvector/HNSW claim is a *migration-layer* claim, and CLAUDE.md requires migrations to replay from empty — so this half is locally decidable rather than 3B-only.
- **Result**: `CREATE DATABASE` → **replay from empty SUCCEEDED, 37 migrations base → head in one run** (`9e6877432c14` … → `8509c0486d8d`), `alembic current` = `8509c0486d8d (head)`, `alembic heads` = `8509c0486d8d (head)` (single head) → `DROP DATABASE`, confirmed absent from `\l`. `packages/db/tests/` exit 0, 6.3s — collected 83 / passed 83 / failed 0 / skipped 0. The URL override was determinable without reading `.env` (`packages/db/alembic/env.py:31-34` + `DEFAULT_DATABASE_URL` at `engine.py:18`), and none of `DB_USERNAME/DB_HOST/DB_PORT/DB_NAME/DATABASE_URL` was set in the shell.
- **What it proves**: The migration chain including the pgvector/HNSW index migrations replays cleanly from an empty database to a single head; the whole `packages/db` suite passes.
- **What it does NOT prove**: The deployed resources — two Fargate services, the RDS engine versions, the VPC layout — are live-AWS facts (3B). Replay-from-empty says nothing about whether staging's *existing* schema matches head.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (migration half)**; deployed half remains 3B.

#### ARCH-12
- **Claim ID**: ARCH-12 — one uvicorn worker per task: neither container definition sets `command`/`entryPoint` and neither Dockerfile CMD passes `--workers`, so a single task cannot exceed 1024 CPU units and the lever is task count.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `grep -n "CMD" apps/learning-api/Dockerfile apps/chat-api/Dockerfile`; `grep -nE '"command"|entryPoint|entrypoint' terraform/modules/ecs-service/main.tf`; `grep -rn -- "--workers" apps terraform .github Makefile docker-compose.yml`; `grep -rn "command" terraform/ --include="*.tf"`
- **Why relevant**: Concurrency per task is the difference between "buy a bigger task" and "buy more tasks", and it is fully decidable from two Dockerfiles plus one module.
- **Result**: both CMDs are plain `uvicorn … --host 0.0.0.0 --port 800{1,2} --proxy-headers --forwarded-allow-ips=* --timeout-keep-alive 125` (`learning-api/Dockerfile:125`, `chat-api/Dockerfile:83`) with **no `--workers`**. `ecs-service/main.tf` `command`/`entryPoint` grep → **exit 1, no matches**. The only `--workers` hit repo-wide is a *comment* acknowledging the absence (`terraform/environments/staging/main.tf:429`). Container-command overrides exist only for the `scheduled-jobs` ops task.
- **What it proves**: Both API containers run a single uvicorn worker and nothing overrides the image default, so the repo's own stated consequence holds — vertical sizing past 1024 CPU units buys nothing and the only real lever is task count.
- **What it does NOT prove**: Measured throughput or latency per task (3B), and nothing about what the live task definition currently is.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (config half)** — confirmed as claimed by executed greps.

#### ARCH-29
- **Claim ID**: ARCH-29 — the doc's "single `langsmith_tracing_enabled` flag gates NAT+tracing" is superseded by D-406's two-consumer map; D-419's "NAT absent from the plan entirely" is false at config level (count = 1 under defaults).
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -n -A12 "private_egress_consumers" terraform/environments/staging/main.tf` (same run as COST-28).
- **Why relevant**: The claim is about *which expression* drives NAT, which is one grep.
- **Result**: `local.private_egress_consumers = { langsmith_tracing = var.langsmith_tracing_enabled, youtube_sync = var.youtube_sync_enabled }`, `needs_private_egress = anytrue(values(local.private_egress_consumers))`, `nat_gateway_enabled = local.needs_private_egress` (`:115-136`), with the D-406 comment recording that the prior `nat_gateway_enabled = var.langsmith_tracing_enabled` form "became a trap the moment a second one existed".
- **What it proves**: The two-consumer map exists and is wired; NAT is provisioned iff either consumer flag is on, so it is not defaulted-on and cannot be orphaned when only one consumer is disabled.
- **What it does NOT prove**: `terraform.tfvars` is unreadable by instruction and `terraform plan` is forbidden, so the **actual** count is indeterminate and the D-419 tension is unresolved (3B). The map is hand-maintained: a third egress consumer has to be registered by a human and nothing mechanical fails if it is not.
- **Revised evidence classification**: unchanged — evidence strengthened (mechanism confirmed by executed grep; resolution remains 3B).

#### ARCH-30
- **Claim ID**: ARCH-30 — four observability sinks; exactly 4 Bedrock metric filters per service; per-task `otel-collector` sidecar; LangSmith masking. LOW drift: masking is enforced in application code, not a task definition.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `uv run pytest packages/observability/tests/test_langsmith_config.py …` (batch 2, same run as SEC-23 / COST-27).
- **Why relevant**: If masking lives in application code, then only executing that code's test verifies it — a task-definition read would miss it entirely.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0. `test_enables_tracing_with_forced_masking_when_a_key_is_present` passed.
- **What it proves**: The masking half is executed-verified in application code, which is exactly where the LOW drift says it lives.
- **What it does NOT prove**: "Data never leaves AWS" and "the sidecar is running per task" are live facts (3B); the per-service metric-filter count was not re-counted here.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (masking half)**; sinks/sidecar remain 3B.

#### ARCH-33
- **Claim ID**: ARCH-33 — the ECS deploy gate is exactly as documented (one PRIMARY, tag match outside the retry, `runningCount ≥ 1`, bounded 300 s), but the Vite content-hash comparison `ARCHITECTURE.md` presents as the frontend half is not in the pipeline — no hash step, no make target, no script.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -nE "sha256|md5|ETag|content-hash|dist/|vite" .github/workflows/deploy-staging.yml`; `grep -nE "s3 sync|s3 cp|create-invalidation|npm run build|npm ci" .github/workflows/deploy-staging.yml`
- **Why relevant**: The claim is a negative over a single 711-line workflow file — the cheapest and most conclusive kind of local check.
- **Result**: **only two lines match, both `dist/`** (`:669`, `:674` — the two `aws s3 sync … --delete`); **no `sha256`, `md5`, `ETag`, or `content-hash` anywhere**, and the literal `vite` never surfaces (the step calls `npm run build`). The pipeline is `npm ci` → `npm run build` → `s3 sync --delete` → blanket `create-invalidation --paths "/*"` → two `curl -sf` liveness checks plus a `/me` 401 probe. The workflow's own comment at `:677-711` reads: "The first two curls only prove the S3 origin serves the SPA - they would pass against a completely stale deployment, and they never touch the API."
- **What it proves**: No step compares the built artefact to the served artefact. A silently-failed sync or a cached edge object is undetectable by CI — and the workflow concedes it in its own comment.
- **What it does NOT prove**: Whether the ECS gate has ever *fired* (3B); the `/me` 401 probe does have teeth for edge routing but says nothing about asset freshness.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (repo half)**, additionally strengthened by the workflow's own comment conceding the curls "would pass against a completely stale deployment".

#### ARCH-35
- **Claim ID**: ARCH-35 — the org time convention is a provisional default with an env switch, and there are **three** variables, not two: `ORG_TIMEZONE`, `ORG_TIME_CONVENTION`, `ORG_TIME_CONFIRMED`.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `grep -n "ORG_TIME" terraform/environments/staging/main.tf` (plus the variable defaults in `variables.tf` and the consumer sites in `packages/shared/src/intellichoice_shared/org_time.py`).
- **Why relevant**: A "two variables" claim is refuted or confirmed by one grep, and the third variable changes what the convention *means*.
- **Result**: three variables set **identically for both services** (learning-api `:497-499`, chat-api `:582-584`). Defaults: `org_timezone = "America/Chicago"`, `org_time_convention = "local_dst_aware"` (validated against `["local_dst_aware","legacy_fixed_utc_minus_6"]`), `org_time_confirmed = false`. Consumers: `org_time.py:53-55`, with `:19` recording "…which is not the same as knowing. Until the org confirms, `ORG_TIME_CONFIRMED` stays false".
- **What it proves**: All three are wired, plumbed identically into both task definitions, and read by one shared module that both server and client depend on, so the two cannot drift. `org_time_confirmed` defaults to **false** — staging runs on an *assumed* `America/Chicago`, honestly labelled as a guess.
- **What it does NOT prove**: The grade-on-submit half and the S43-owed property guard are frozen with S43 (integration deferred, D-152); the live env var values are 3B and tfvars is unread.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (config half)** — three-variable finding confirmed by executed grep.

### 2.3 SEC family

#### SEC-04
- **Claim ID**: SEC-04 — 4 of 6 authorization-matrix rows enforced in the query layer; tutor/branch_manager not enforced per-student (D-086 accepted); admin has no backend enforcement because no admin role exists in `Role`.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest apps/chat-api/tests/test_role_access.py packages/db/tests/test_rag_search.py …` — same run as TEST-02, batch 1.
- **Why relevant**: Non-negotiable rule 3 — authorization in the query layer, never in prompts. These two suites are where the pre-retrieval filter is asserted.
- **Result**: exit 0, inside `183 passed` (0 failed / 0 skipped).
- **What it proves**: The four enforced rows execute and pass: role/branch filters are applied before RAG retrieval in code.
- **What it does NOT prove**: The absent admin role cannot be confirmed absent by execution, and "should an admin role exist" is a product decision. The two unenforced rows are accepted by D-086, not fixed.
- **Revised evidence classification**: unchanged — evidence strengthened.

#### SEC-05
- **Claim ID**: SEC-05 — the Postgres PII floor: no model has a PII column name.
- **Previous Phase 3A classification**: CONFIRMED (cited test unexecuted)
- **Command executed**: `uv run pytest packages/db/tests/test_schema_purity.py …` — same run as TEST-02, batch 1 (and again inside batch 8's `packages/db/tests/`, 83 passed).
- **Why relevant**: Non-negotiable rule 1. The test walks `Base.registry.mappers`, so its verdict changes with any new model — exactly the kind of check whose value is only realised by running it.
- **Result**: exit 0, inside `183 passed`; independently re-run inside batch 8 (collected 83 / passed 83 / failed 0 / skipped 0).
- **What it proves**: `test_no_model_has_a_pii_column_name` passes over every currently registered ORM model.
- **What it does NOT prove**: **It does not cover the LangGraph checkpoint tables**, which are not ORM models (REQ-52's limitation) — so checkpointed state is outside the floor's reach, confirmed rather than closed.
- **Revised evidence classification**: unchanged — evidence strengthened.

#### SEC-06
- **Claim ID**: SEC-06 — every Bedrock payload is governed by one regime, and every nested model is itself governed (no PII in LLM payloads).
- **Previous Phase 3A classification**: CONFIRMED (cited test unexecuted)
- **Command executed**: `uv run pytest packages/shared/tests/test_bedrock_payload_pii_floor.py …` — same run as TEST-02, batch 1.
- **Why relevant**: Non-negotiable rule 1 again, and this is the only mechanism that fails on a *new* payload class — the pinning is the load-bearing part, especially given TEST-04's 31→41 count drift.
- **Result**: exit 0, inside `183 passed` (0 failed / 0 skipped).
- **What it proves**: Both governance assertions pass, including the nested-model walk, over the current payload surface.
- **What it does NOT prove**: It governs only the Bedrock payload surface — TEST-04's counts show `extra="forbid"` covers 41 of 184 non-test `BaseModel`/`BaseSettings` classes (22%), so this is not a repo-wide invariant. Nothing here observes an actual payload in flight (3B/external).
- **Revised evidence classification**: unchanged — evidence strengthened.

#### SEC-10
- **Claim ID**: SEC-10 — `learning_checkpoint_repairs_total` exists, is incremented at one site, is promoted to CloudWatch and rendered on a dashboard, but no alarm watches it, so nothing can page on the exact event that voids the §7-R9 acceptance.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -rn "checkpoint_repair" terraform/`; `find terraform -name "alarms*.tf"`; `grep -nE 'resource "aws_cloudwatch_metric_alarm"|metric_name' terraform/modules/observability/alarms.tf`
- **Why relevant**: The negative grep is the whole evidence, so its exact extent matters.
- **Result**: **4 lines, not 3** — `terraform/modules/ecs-service/main.tf:209` (otel `filter/kpis` scrape allowlist), `:255` (`awsemf` `metric_declarations`, the EMF promotion), `terraform/modules/observability/dashboard.tf:425` (a comment: "Should sit at zero. `checkpoint_repairs` is AUD-X-07's canary"), `:436` (the dashboard widget line). `alarms.tf` is the only alarms file and holds **8 alarms**, on `BedrockCircuitOpen`, `LangSmithIngestFailed`, `BedrockCallFailed`, `CPUUtilization`, `FreeStorageSpace`, `DatabaseConnections`, `MemoryUtilized`, `BedrockCostCents` — **none references the metric**.
- **What it proves**: The metric is scraped, EMF-promoted and charted, and its own dashboard comment calls it a canary that "should sit at zero" — yet no `aws_cloudwatch_metric_alarm` watches it anywhere, so a checkpoint-repair burst is silent until a human opens the dashboard.
- **What it does NOT prove**: Whether the metric has ever been non-zero in staging (3B). `test_alarm_severity_routing.py` would **not** catch this: it routes alarms that exist, it does not require an alarm per tripwire metric.
- **Revised evidence classification**: unchanged — **3A wording corrected (LOW)**: 4 `checkpoint_repair` lines in terraform, not 3 (two metric-pipeline lines in `ecs-service/main.tf`, one comment, one dashboard widget). Substance unchanged: no alarm references it.

#### SEC-12
- **Claim ID**: SEC-12 — location notice verbatim pre-collection; coordinates function-local in `branch_locator`; MCP audit rows carry no arguments; manual address persists only in `checkpoint_writes.__resume__`, deleted on the success path only (couples to SEC-13).
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest apps/chat-api/tests/test_branch_locator.py …` (batch 7-iv, same run as REQ-28 / REQ-44 / COST-17).
- **Why relevant**: The 3A block cited no test; this uncited suite is the only thing that exercises the locator path end to end locally.
- **Result**: exit 0, 8.2s — collected 43 / passed 43 / failed 0 / skipped 0.
- **What it proves**: The branch-locator path executes and passes, consistent with coordinates staying function-local (cross-checked by REQ-52: `QAState` has no coordinate field).
- **What it does NOT prove**: LangSmith trace payloads are external SaaS (never repo-verifiable). The `__resume__` persistence half is SEC-13's finding and is **untested** — see below.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (code half)**; trace-payload half external, `__resume__` half unexecuted.

#### SEC-13
- **Claim ID**: SEC-13 — NEW MATERIAL DRIFT (privacy/minors): `purge_resume_writes` has exactly one trigger, the successful-resume path. A cancelled resume returns before it (`sessions.py:897-905` precedes `:907-914`) and any exception in `_run_turn` skips it, leaving coordinates/address in `checkpoint_writes`.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `grep -rln "purge_resume_writes" apps packages --include="*.py"`; `grep -rn "purge_resume_writes" apps packages --include="*.py"`
- **Why relevant**: The claim is "no test covers this". A file-list grep is the exact instrument for that, and it either finds a test file or it does not.
- **Result**: **3 files, all under `src/`** — `apps/chat-api/src/chat_api/routers/sessions.py` (`:66` import, `:914` the single `await`), `apps/chat-api/src/chat_api/graph/nodes.py:801` (an explanatory comment), `apps/chat-api/src/chat_api/services/checkpoint_privacy.py:24` (the definition). **Zero test files** — no `tests/` path appears in the result set.
- **What it proves**: The function that scrubs resume-write payloads out of the checkpointer — the §5.30 no-PII boundary for a minor's location — has **no test asserting it removes anything**, and its single call site is one `await` inside a router, so a refactor deleting that line would break no test.
- **What it does NOT prove**: The cancel-path leak itself is still a **code-path claim, not an executed one**. A new pytest (cancelled resume → assert the `__resume__` row survives) would settle it entirely locally against the dev Postgres; authoring new test code is out of audit scope and is recorded in §3 as one of the three highest-value new-test candidates.
- **Revised evidence classification**: unchanged — evidence strengthened (grep-only: **zero test files confirmed**); the leak itself remains unexecuted.

#### SEC-23
- **Claim ID**: SEC-23 — LangSmith masking forced (assignment, not `setdefault`) with a test asserting it is not optional; per-environment project real via `LANGSMITH_PROJECT = var.name_prefix`; retention has no in-repo expression at all.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest packages/observability/tests/test_langsmith_config.py …` (batch 2, same run as COST-27 / ARCH-30).
- **Why relevant**: "Assignment, not `setdefault`" is a difference only a test can demonstrate — the distinction is invisible unless the environment tries to opt out.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0. `test_enables_tracing_with_forced_masking_when_a_key_is_present` passed.
- **What it proves**: Masking is **not optional**: the assertion that env cannot opt out of `LANGSMITH_HIDE_INPUTS`/`_OUTPUTS` executes and passes (SPEC §5.32.1 is quoted inline in the test at `:39-40`).
- **What it does NOT prove**: What the SaaS actually received (external). **Retention is a LangSmith-side account setting — nothing in the repo would detect its absence**, so it stays unverifiable from here.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (masking half)**; retention half remains org-external.

#### SEC-25
- **Claim ID**: SEC-25 — D-085's `/dev/token` incident: the fix is three layered mechanisms (env + flag + shared secret), checked in HTTP middleware before routing and again in the handler, with `hmac.compare_digest` and fail-closed on an unconfigured secret.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `uv run pytest apps/learning-api/tests/test_stream_and_history.py -k "token or staging" -q -rA` (batch 7-i).
- **Why relevant**: This is a *real incident's* fix. Defence-in-depth, fail-closed, and 404-not-403 are behavioural properties, so only execution is evidence.
- **Result**: exit 0, 13.5s — collected 25 / selected 16 (9 deselected) / passed 16 / failed 0 / skipped 0.
- **What it proves**: The gate logic executes and passes, including "404s on staging without the shared secret" and "closed is indistinguishable from an absent path". Combined with ARCH-03's exhaustive grep, `/dev/token` is the only token-issuing route in the repo.
- **What it does NOT prove**: Whether the route is **currently** secret-gated on the live ALB (3B). No secret value was read or printed at any point.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (gate logic)** — 16 gate tests passed; live ALB reachability remains 3B.

### 2.4 COST family

#### COST-03
- **Claim ID**: COST-03 — the circuit breaker opens after threshold and blocks further calls, caps provider calls even under a concurrent failure burst, and a provider outage still opens the circuit.
- **Previous Phase 3A classification**: CONFIRMED (cited tests unexecuted)
- **Command executed**: `uv run pytest packages/adapters/tests/test_bedrock_gateway.py …` (batch 4, same run as REQ-19).
- **Why relevant**: Treat cost bugs as production bugs. The concurrent-burst case is the one that actually bounds spend, and concurrency tests are the class most likely to pass by construction and fail in practice — so running it is the point.
- **Result**: exit 0, 3.2s — collected 44 / passed 44 / failed 0 / skipped 0 / errors 0, including the concurrent failure-burst breaker test.
- **What it proves**: The breaker bounds provider calls under a concurrent failure burst, not merely under sequential failures.
- **What it does NOT prove**: The breaker's behaviour under real Bedrock throttling or a real account cap (3B/paid). It bounds *call count*, and COST-10 shows the reserve step misprices large inputs, so call-count bounding is not spend bounding.
- **Revised evidence classification**: unchanged — evidence strengthened (adjudicated jointly with REQ-19 as **LOCALLY_VERIFIED** for the six gateway cost features, 44/44).

#### COST-06
- **Claim ID**: COST-06 — `skipped_duplicate_id` is claimed untested and money-attributable-to-run-total; in fact a test exists **and** the `run_plan` flush-time branch loses the spend entirely (skips both `spend +=` and `_settle`).
- **Previous Phase 3A classification**: **CONFLICT**
- **Command executed**: `uv run pytest "packages/curriculum/tests/test_authored_pipeline.py::test_per_candidate_settlement_survives_a_duplicate_id" …` (batch 3a, same run as REQ-20).
- **Why relevant**: Half (a) — the `_settle` commit-time branch — is exactly what this test covers, so execution moves half of a two-halved conflict.
- **Result**: exit 0, 2.5s — collected 2 / passed 2 / failed 0 / skipped 0.
- **What it proves**: The commit-time settlement branch survives a duplicate id, executed. Half (a) is now executed evidence rather than existence.
- **What it does NOT prove**: **Half (b) is untouched.** The flush-time `IntegrityError` branch that drops the spend (the `continue` at `pipeline_cli.py:618` preceding `spend += outcome.cost_cents` at `:619`) has **no test in the repo**; the loss is demonstrated by code path only. Authoring that test is out of audit scope (recorded in §3), though the fake gateway would suffice — no paid run needed.
- **Revised evidence classification**: **unchanged (CONFLICT)** — one half strengthened to executed evidence, the other half still has no test.

#### COST-10
- **Claim ID**: COST-10 — MEDIUM drift: D-141's input-token bound is not in the gateway (which bounds output only and uses a hardcoded 2000-token pricing assumption); it lives in `packages/memory/consolidation.py` as `_MAX_EVENT_TOKENS_PER_CALL = 20_000`, sized against the 20 s timeout.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest packages/memory/tests/test_consolidation.py …` (batch 6); `grep -rniE "max_input|MAX_PROMPT|D-141" packages/adapters/src packages/shared/src --include="*.py"`; `grep -n "_MAX_EVENT_TOKENS_PER_CALL" packages/memory/src/intellichoice_memory/consolidation.py`
- **Why relevant**: Rule 7 requires max-token limits at the gateway seam; the question is whether the limit exists there or only in one voluntary caller.
- **Result**: batch 6 exit 0, 5.2s — collected 55 / passed 55 / failed 0 / skipped 0. Gateway grep **exit 1 → no matches**. What exists: `_MAX_EVENT_TOKENS_PER_CALL = 20_000` (`consolidation.py:103`), `_CHARS_PER_TOKEN = 3.0`, `_MAX_CALLS_PER_STUDENT = 4`; and in the gateway, output only — `_HARD_MAX_OUTPUT_TOKENS = 4000` (`gateway.py:78`), applied at `:236`.
- **What it proves**: **Sharpened, mechanism now precise.** `gateway.py:182-194` `worst_case_cost_cents` reserves with a **hard-coded 2000-token input assumption** — `self._cost_cents(model_id, 2000, min(max_output_tokens, _HARD_MAX_OUTPUT_TOKENS))` — and the docstring concedes it is "inherited rather than re-guessed". So a large-input call is **neither refused nor correctly priced at the reserve step**. Input bounding is per-caller and voluntary, not enforced at the seam.
- **What it does NOT prove**: **Not traced in this phase: whether settlement uses actual input tokens** (which would bound the exposure to the reserve-settle window). Coverage across other paid callers (RAG context assembly, tutor-chat history) is unestablished and untested.
- **Revised evidence classification**: unchanged — **SHARPENED (MEDIUM stands)**; the consolidation bound as implemented is LOCALLY_VERIFIED, the gateway absence re-confirmed at zero hits.

#### COST-13
- **Claim ID**: COST-13 — request logging and background-task trace join: a detached task logs the trace id of the request that spawned it, and a task spawned outside a span carries no trace id.
- **Previous Phase 3A classification**: CONFIRMED (cited tests unexecuted)
- **Command executed**: `uv run pytest packages/observability/tests/test_request_logging.py packages/observability/tests/test_background_task_trace_join.py …` (batch 2).
- **Why relevant**: Both directions are asserted (D-221's rule), and trace-join correctness is what makes every later X-Ray/log reading trustworthy — a silent break here poisons the instruments used in 3B.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0.
- **What it proves**: The join works in the positive direction and the negative control holds — a task with no parent span carries no trace id, so trace ids are not fabricated.
- **What it does NOT prove**: That deployed traces actually arrive at X-Ray / LangSmith (3B and external); local passes say nothing about the collector sidecar.
- **Revised evidence classification**: unchanged — evidence strengthened.

#### COST-16
- **Claim ID**: COST-16 — `aws_budgets_budget.monthly` with two notifications (ACTUAL > 80%, FORECASTED > 100%), $20 default; the three `bedrock_*` circuit/budget settings exist in both app Settings and six package settings modules. LOW drift: "scale `desired_count` to 0" is not literally effective on a live service.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `grep -rn "bedrock_session_budget_cents\|bedrock_circuit_failure_threshold\|bedrock_circuit_cooldown_s" apps/learning-api/src/learning_api/config.py apps/chat-api/src/chat_api/config.py`
- **Why relevant**: The settings-declaration half is the only part of a budget claim that is repo-decidable, and whether the two apps agree is a one-grep question.
- **Result**: `bedrock_circuit_failure_threshold: int = 5`, `bedrock_circuit_cooldown_s: float = 30.0`, `bedrock_session_budget_cents: float = 50.0` — at `learning-api/config.py:119-121` and `chat-api/config.py:80-82`, **identical line-for-line in both apps**.
- **What it proves**: The three settings exist with the claimed values in both apps; there is no per-app tuning. The ceiling is **per session**, which is the unit the claim should name — 50¢ × N concurrent sessions is the real exposure, and neither file carries a per-day or per-account ceiling.
- **What it does NOT prove**: Whether the AWS budget notification is actually delivering (3B); the $20 budget resource itself was not re-read here; and the LOW `desired_count` drift is a live-service behaviour (`ignore_changes` + autoscaling own it).
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (settings-declaration half)** — confirmed exactly as claimed by executed grep.

#### COST-17
- **Claim ID**: COST-17 — P1-5 fully confirmed: a `$.event="client_error"` metric filter per log group plus a per-service alarm (period 900, Sum > 0, `notBreaching`) routed to the page channel, matching D-419.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `uv run pytest apps/chat-api/tests/test_client_errors.py apps/learning-api/tests/test_client_errors.py …` (batch 7-iv, same run as REQ-28 / REQ-44 / SEC-12).
- **Why relevant**: The alarm only ever fires if the *reporting* endpoint actually emits the `client_error` event, so the reporting half is the precondition for the whole mechanism.
- **Result**: exit 0, 8.2s — collected 43 / passed 43 / failed 0 / skipped 0. (`apps/learning-api/tests/test_client_errors.py` exists and was included.)
- **What it proves**: The client-error reporting routers on both apps execute and pass — the event the filter keys on is produced.
- **What it does NOT prove**: Deployed existence of the metric filter and the alarm, and whether either has ever fired (3B).
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (reporting half)**; filter/alarm existence remains 3B.

#### COST-19
- **Claim ID**: COST-19 — P1-7 confirmed: four heartbeat alarms from `for_each = toset(var.nightly_job_events)`, `LessThanThreshold`, period 172800, `treat_missing_data = "breaching"`, routed to the page channel, with a matching metric filter that deliberately has no `default_value`.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `uv run pytest packages/observability/tests/test_alarm_severity_routing.py …` (batch 2, same run as COST-23 / COST-24 / WORK-08 / REQ-49).
- **Why relevant**: These tests **parse the real terraform files**, so they are terraform evidence that runs entirely locally — the rare case where a config claim has an executable leg.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0. The 3 `test_alarm_severity_routing.py` tests parsed the real `.tf` files and passed.
- **What it proves**: The routing property of the heartbeat alarms is executed-verified against the actual terraform source, not read by eye.
- **What it does NOT prove**: Whether the four alarms exist in AWS and are `OK` (3B). **Config is not deployed** — `terraform apply` is not part of `deploy-staging.yml`, and tfvars is unread.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (config-parsing half)**; deployed existence remains 3B.

#### COST-23
- **Claim ID**: COST-23 — the single-inbox state is superseded in configuration (two SNS topics, each with its own subscription) but delivery is still one address by default (`informational_notification_email` default null, no staging setter). The audit's "26 alarms" is a pre-D-377 count; today's config is 15 alarm resources → ~30 instances.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `uv run pytest packages/observability/tests/test_alarm_severity_routing.py …` (batch 2 — same run as COST-19 / COST-24 / WORK-08 / REQ-49).
- **Why relevant**: `test_every_alarm_notifies_exactly_one_severity_channel` is the mechanical guard for "no alarm carries both topics", which is the property the two-topic split depends on.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0.
- **What it proves**: The one-channel-per-alarm property holds against the real terraform source, executed.
- **What it does NOT prove**: tfvars is unread, so the *delivery* address is indeterminate; live subscription state (including `PendingConfirmation`) is 3B. The alarm-count arithmetic (15 resources → ~30 instances) was not re-counted here.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (config-parsing half)**; delivery and subscription state remain 3B.

#### COST-24
- **Claim ID**: COST-24 — the alarm-severity routing guards: every alarm notifies exactly one severity channel, the 500 and spend alarms are never quiet, and the quiet channel is exactly the reviewed list.
- **Previous Phase 3A classification**: CONFIRMED (cited tests unexecuted)
- **Command executed**: `uv run pytest packages/observability/tests/test_alarm_severity_routing.py …` (batch 2).
- **Why relevant**: This is the **only** mechanical guard against an unrouted alarm or a quietly-demoted outage alarm, and it also serves COST-19, COST-23, WORK-08 and REQ-49's routing half.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0. The 3 routing tests parse the real terraform files and passed.
- **What it proves**: No alarm in the checked-in terraform is unrouted or carries two severity channels; the quiet channel matches the reviewed list. The terraform-parsing tests passed, so the config claims that ride on them carry executed local evidence.
- **What it does NOT prove**: **Config is still not deployed.** Nothing here says an alarm exists in AWS, is in `OK`, or has ever notified anyone.
- **Revised evidence classification**: CONFIRMED → **LOCALLY_VERIFIED (config-parsing half)**; deployed state remains 3B.

#### COST-27
- **Claim ID**: COST-27 — `configure_langsmith()` no-ops without a key and otherwise unconditionally assigns `LANGSMITH_HIDE_INPUTS`/`_OUTPUTS = "true"` (assignment, not `setdefault`, so env cannot opt out); the D-242 `LangSmithIngestFailed` filter + alarm exist per service, routed to `alerts_info` deliberately rather than the page channel.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `uv run pytest packages/observability/tests/test_langsmith_config.py …` (batch 2, same run as SEC-23 / ARCH-30).
- **Why relevant**: "Env cannot opt out" is a claim about *code shape* whose only proof is a test that tries to opt out and fails.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0; the masking-not-optional test passed (assignment, not `setdefault`), with SPEC §5.32.1 quoted inline at `test_langsmith_config.py:39-40`.
- **What it proves**: Masking is unconditional in code and cannot be disabled through the environment.
- **What it does NOT prove**: What the SaaS actually received (external); the alarm's deployed existence and its `alerts_info` routing in AWS (3B).
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (masking half)**.

#### COST-28
- **Claim ID**: COST-28 — NAT is keyed to a map of two consumers, not to `langsmith_tracing_enabled`, so the claim's own wording is stale; under current defaults `needs_private_egress = true` → NAT enabled by configuration.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `grep -n -A12 "private_egress_consumers" terraform/environments/staging/main.tf` (same run as ARCH-29).
- **Why relevant**: Whether NAT follows one flag or a map decides whether the $33/mo can be silently orphaned.
- **Result**: `:115-119` the two-entry map plus `needs_private_egress = anytrue(values(...))`; `:136 nat_gateway_enabled = local.needs_private_egress`; D-214/D-406 comments at `:128-134`; `:845-846` the single `youtube_sync_enabled` switch.
- **What it proves**: The mechanism is present and correct as far as it goes — NAT cannot be orphaned when only one consumer is disabled, which is the D-406 trap the prior single-flag form created.
- **What it does NOT prove**: Whether a NAT gateway actually exists in AWS (D-419's contradiction) and the idle-cost note are 3B; tfvars is unread. **There is no test or `terraform validate` rule tying the hand-maintained map to actual outbound callers**, so a third consumer added later breaks at runtime with nothing failing first.
- **Revised evidence classification**: unchanged — evidence strengthened (config half confirmed by executed grep).

#### COST-29
- **Claim ID**: COST-29 — MEDIUM drift: D-136's price table was measured on a 256/512 task; learning-api now runs 512/1024 (task count unchanged at 2), and chat-api runs on module defaults 256/512, so the two services are not the same size. `ARCHITECTURE.md:254-283` quotes the table as current.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `grep -nE "^\s*(cpu|memory|desired_count|autoscaling_min_capacity|autoscaling_max_capacity)" terraform/environments/staging/main.tf`; then the chat-api module range (`sed -n '517,652p' … | grep -nE "cpu|memory|desired_count|autoscaling"`); plus the module defaults in `terraform/modules/ecs-service/variables.tf`.
- **Why relevant**: The asymmetry is expressed by *omission*, so it is only visible if you check both modules and then the defaults the silent one inherits.
- **Result**: **4 lines total, all inside `module "ecs_service_learning_api"`** — `:432 cpu = 512`, `:433 memory = 1024`, `:446 desired_count = 2`, `:447 autoscaling_min_capacity = 2`. Inside `module "ecs_service_chat_api"` the only hit is a comment about a reverted `autoscaling_max_capacity = 1`. Module defaults chat-api inherits: `cpu 256`, `memory 512`, `desired_count 1`, `autoscaling_min_capacity 1`, `autoscaling_max_capacity 3`.
- **What it proves**: The two services are asymmetric **by omission rather than by decision** — chat-api sets none of the four and silently inherits a single task at one-quarter the CPU, with no measurement cited either way, so losing chat-api's one task loses all chat capacity. Carried from the same comment: **`terraform apply` is not part of `deploy-staging.yml`**, so any of these numbers can differ from live.
- **What it does NOT prove**: Live task size and count are 3B; nothing here re-validates D-136's price arithmetic.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (config half)** — confirmed as claimed by executed greps; MEDIUM drift stands.

### 2.5 TEST family

#### TEST-02
- **Claim ID**: TEST-02 — TRACEABILITY's "unverified counts as not traced" rule is stated as claimed and all five sampled tranche-1 rows cite artifacts that exist (14/14 files, 2/2 function names) — but "would fail if the requirement broke" is the rule's actual substance and is unverifiable without execution. Row 5's implementation cite is stale.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest packages/db/tests/test_schema_purity.py packages/shared/tests/test_bedrock_payload_pii_floor.py packages/observability/tests/test_tracing.py apps/learning-api/tests/test_exam_policy.py apps/learning-api/tests/test_mastery_bootstrap.py apps/learning-api/tests/test_report.py apps/learning-api/tests/test_exam_flow_determinism.py packages/db/tests/test_rag_search.py apps/chat-api/tests/test_role_access.py apps/learning-api/tests/test_learning_graph_routes.py apps/chat-api/tests/test_calendar_action.py apps/chat-api/tests/test_admin_escalation.py apps/learning-api/tests/test_auth_and_attendance.py -q -rA` (batch 1).
- **Why relevant**: The §2.6 criterion-1 rule's whole substance is "the test would fail if the requirement broke", and existence cannot speak to that. 13 of the 14 cited artifacts are pytest files.
- **Result**: exit 0, 20.2s wall — collected 183 / passed 183 / failed 0 / skipped 0 / errors 0. Summary line: `183 passed in 18.90s`.
- **What it proves**: **The largest single evidence conversion in this phase.** All five sampled criterion-1 rows move from "artifact exists" to "artifact passes" — 183/183 across the 13 cited files.
- **What it does NOT prove**: A pass is not proof the test *would fail* on a broken requirement; that needs deliberate mutation, not execution. `scripts/scan_logs_pii.py` (the 14th artifact) needs staging CloudWatch and was not run (3B). Row 5's stale implementation cite is documentary and untouched.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (repo half)** — 183/183 across the 13 cited files.

#### TEST-04
- **Claim ID**: TEST-04 — all six structural rows' artifacts exist; two are declared descriptive by design. Drift LOW: the `extra="forbid"` count is stale (41 in non-test source, not 31), and pyright does not fail when an `extra="forbid"` is deleted — only the Bedrock-payload subset is test-pinned.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `make typecheck`; `grep -rc 'model_config = ConfigDict(extra="forbid")' apps packages --include="*.py" | awk -F: '$2>0'`; `grep -r … | wc -l`; the non-test-filtered variant; `grep -rnE 'class [A-Za-z0-9_]+\((BaseModel|BaseSettings)' apps packages --include="*.py" | grep -vE '(^|/)tests?/|/test_[^/]*\.py:' | wc -l`; `grep -n 'forbid' docs/TRACEABILITY.md`.
- **Why relevant**: The declared §5.27 mechanism **is** `make typecheck`, so running it is the direct test of clause (b); the count is a one-command arithmetic check.
- **Result**: `make typecheck` exit 0 — `0 errors, 0 warnings, 0 informations`. Count: **41**, and the non-test-filtered count is also **41** (zero of the 41 are in test files), concentrated in **4 files** with 35 of them in `packages/shared/src/intellichoice_shared/bedrock.py` alone. No other `ConfigDict` variant exists anywhere. Denominator: **184** non-test `BaseModel`/`BaseSettings` classes; `bedrock.py` itself has 64 `BaseModel` classes of which 35 carry `extra="forbid"`. `docs/TRACEABILITY.md:623` and `docs/DECISIONS.md:6870` both cite **31**.
- **What it proves**: The clause-(b) mechanism executes clean, and the documented figure is stale/low by 10. Strictness covers **41 of 184** non-test model classes (22%), so "types every payload as an `extra=forbid` model" is true for the Bedrock payload surface but is **not a repo-wide invariant**.
- **What it does NOT prove**: "Does the mechanism fail when the artifact is removed" would need a deliberate mutation, which was not performed — so the LOW drift about pyright not catching a deleted `extra="forbid"` stands unexecuted.
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (mechanism half)**; the 41-vs-31 drift confirmed by executed count.

#### TEST-09
- **Claim ID**: TEST-09 — T-01 closed with two opposite answers: CloudTrail wired (built), GuardDuty absent and annotated (deferred, D-125).
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `grep -rni "guardduty" terraform/`; `grep -rni "guardduty" docs/ --include="*.md"`
- **Why relevant**: "Absent" and "absent by decision" are different audit findings, and the disposition trail is in the repo.
- **Result**: terraform — **2 matches, both comments, zero resources** (`staging/main.tf:740`, `modules/cloudtrail/main.tf:10`, both cost-rationale). Docs — `docs/TRACEABILITY.md:649` records T-01 closed 2026-07-30 (D-125) as two opposite answers; `:715`, `:719` ("GuardDuty is still absent; it is now *absent and accounted for*"), `:736`.
- **What it proves**: No `aws_guardduty_*` resource exists, and the absence is dispositioned rather than an oversight — deferred to S50 A7 with a written reason. An audit line should say "absent by decision (D-125), tracked to S50 A7", not "missing".
- **What it does NOT prove**: CloudTrail's `IsLogging: true` and the delivery proof are runtime facts (3B).
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (repo half)** — confirmed as claimed by executed greps; CloudTrail runtime half remains 3B.

#### TEST-12
- **Claim ID**: TEST-12 — `test_editing_an_item_already_in_the_database_propagates`: an edit lands, and a breaking edit fails the load. The block explicitly flags that the test needs a live DB and **may be silently skipped**.
- **Previous Phase 3A classification**: CONFIRMED (with a TEST_EXISTS_NOT_EXECUTED limitation)
- **Command executed**: `uv run pytest … "packages/curriculum/tests/test_authored_bank.py::test_editing_an_item_already_in_the_database_propagates" -q -rA` (batch 5).
- **Why relevant**: The block's own worry is the *skip*, not the assertion — and a skip is the exact failure mode that a "green suite" hides.
- **Result**: batch 5 exit 0, 4.8s — collected 41 / passed 41 / failed 0 / **skipped 0** / errors 0.
- **What it proves**: The block's own worry is answered: the test **RAN** against the local Postgres — it was not skipped — and it passed. Both halves (edit lands; breaking edit fails the load) are executed.
- **What it does NOT prove**: Nothing about the staging database's contents or a paid authoring run. A local pass does not mean CI is configured to have a DB available.
- **Revised evidence classification**: CONFIRMED (TEST_EXISTS_NOT_EXECUTED limitation) → **LOCALLY_VERIFIED** — and the "may be silently skipped" worry is resolved: it ran.

#### TEST-13
- **Claim ID**: TEST-13 — "traced ≠ enforced": the citation quote floors are now measured constants with band-asserting tests, and the band assertion is only meaningful once executed.
- **Previous Phase 3A classification**: CONFIRMED (cited tests unexecuted)
- **Command executed**: `uv run pytest packages/knowledge/tests/ -k "quote_floor" -q -rA` → **exit 5, collected 0 (`40 deselected in 0.89s`) — NOT evidence**. Recovered by locating the tests with grep and running `uv run pytest apps/chat-api/tests/test_qa_service.py -q -rA`.
- **Why relevant**: The band assertion is a measured constant, so only execution makes it a claim about the code rather than about the comment above it.
- **Result**: recovery run exit 0, 3.6s — collected 23 / passed 23 / failed 0 / skipped 0. Executed and passed: `test_the_quote_floor_is_measured_at_its_own_boundary`, `test_the_floor_is_applied_to_the_normalized_quote`, `test_a_quote_dropped_for_being_too_short_says_so_in_the_log`, `test_the_quote_floor_excludes_only_heading_chunks`, `test_a_one_character_quote_no_longer_verifies`, `test_the_model_is_told_what_a_quote_has_to_be`. Implementation: `apps/chat-api/src/chat_api/services/qa.py`; measurement: `scripts/measure_citation_quote_floor.py`.
- **What it proves**: The quote-floor band assertions execute and pass at their own boundary, including the heading-chunk exclusion and the one-character negative control.
- **What it does NOT prove**: Nothing about live retrieval quality (3B). **Instrument note: the as-briefed command collected 0 and is recorded as not-evidence**, recovered only because the location was re-derived by grep.
- **Revised evidence classification**: unchanged — **3A location corrected (LOW)**: the quote-floor tests live in `apps/chat-api/tests/test_qa_service.py`, **not** `packages/knowledge` as the 3A block implies; tests found and passed.

#### TEST-14
- **Claim ID**: TEST-14 — the reranker-degraded score floor is deliberately not applied, and the degraded path is loud.
- **Previous Phase 3A classification**: **TEST_EXISTS_NOT_EXECUTED**
- **Command executed**: `uv run pytest packages/knowledge/tests/test_retrieval.py -q -rA` (batch 3c-i).
- **Why relevant**: "The floor does not apply when the reranker is unavailable" is a conditional behaviour; a file's existence says nothing about which branch it takes.
- **Result**: exit 0, 0.7s — collected 22 / passed 22 / failed 0 / skipped 0 / errors 0, including `test_the_floor_does_not_apply_when_the_reranker_is_unavailable`. Three tests emit expected `retrieval_rerank_degraded` / `access_probe_rerank_degraded` warnings **by design** — the loudness half, observed.
- **What it proves**: The degraded path both skips the floor and is loud, executed — the whole retrieval suite passes.
- **What it does NOT prove**: That the reranker ever actually degrades in staging, or how often (3B). Fail-closed behaviour under a *real* provider outage is untested here.
- **Revised evidence classification**: TEST_EXISTS_NOT_EXECUTED → **LOCALLY_VERIFIED** — 22/22 retrieval tests passed including the no-floor-when-degraded test.

#### TEST-22
- **Claim ID**: TEST-22 — the six D-383 closure specs/tests for the 2026-08-17 audit's three blind spots exist (five Playwright specs + two pytest error-detail-contract files).
- **Previous Phase 3A classification**: **TEST_EXISTS_NOT_EXECUTED**
- **Command executed**: `uv run pytest apps/learning-api/tests/test_error_detail_contract.py apps/chat-api/tests/test_error_detail_contract.py -q -rA` (batch 3d). Playwright half **not run** (`make e2e` would be the command).
- **Why relevant**: The 2026-08-17 audit's central lesson is that the Playwright suite was green on the same build that carried both P1s — so which half of a closure set has actually executed is the whole question.
- **Result**: exit 0, 13.2s — collected 6 / passed 6 / failed 0 / skipped 0 / errors 0.
- **What it proves**: The six pytest error-detail-contract tests execute and pass on both apps.
- **What it does NOT prove**: The five Playwright specs — `journey-terminal`, `attendance-email-approved`, `escalation-approved`, `error-vocabulary`, `error-states` — **were not executed**. They share the dev Postgres with pytest and need both APIs plus both Vite servers, so they were deliberately deferred by phase design. Their existence remains the only evidence for them.
- **Revised evidence classification**: **SPLIT** — the 6 pytest error-detail-contract tests → **LOCALLY_VERIFIED**; the 5 Playwright specs remain **TEST_EXISTS_NOT_EXECUTED** (deliberately deferred).

#### TEST-23
- **Claim ID**: TEST-23 — API-level interrupt approvals were real: the named tests assert send, recipient, and an `InterruptApproval` row, on both apps.
- **Previous Phase 3A classification**: **TEST_EXISTS_NOT_EXECUTED**
- **Command executed**: `uv run pytest "apps/learning-api/tests/test_learning_flow.py::test_attendance_ask_branch_manager_end_to_end" -q -rA` (batch 3e); `apps/chat-api/tests/test_admin_escalation.py` inside batch 1.
- **Why relevant**: Non-negotiable rule 4 — every external action needs human approval via `interrupt()`. "Sends only after approval" and "declined sends nothing" are behaviours, not artifacts.
- **Result**: batch 3e exit 0, 12.3s — collected 1 / passed 1 / failed 0 / skipped 0. `test_admin_escalation.py` passed inside batch 1's `183 passed` (both `test_admin_escalation_pauses_then_sends_only_after_approval` and `test_admin_escalation_declined_sends_nothing`).
- **What it proves**: Both API halves are executed-verified: the attendance-email end-to-end path on learning-api, and both escalation directions (approved sends; declined sends nothing) on chat-api.
- **What it does NOT prove**: The browser half — `e2e/tests/learning/attendance-email-approved.spec.ts` — was not run; its evidence remains existence only. Nothing here says a real Gmail send would occur (dev fakes).
- **Revised evidence classification**: TEST_EXISTS_NOT_EXECUTED → **LOCALLY_VERIFIED for both API halves**; browser half stays deferred.

#### TEST-27
- **Claim ID**: TEST-27 — `capture.ts` enforces four things at teardown but "zero blank/stuck states" is not one of them, and `assertClean()` runs only when `testInfo.status === "passed"`, so a failing test's criterion-3 evidence is reported and not enforced.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `make e2e-typecheck` (`cd e2e && npx tsc --noEmit`). Behavioural half deferred (`make e2e` not run).
- **Why relevant**: The fixture claim is about code that only runs under Playwright; the one free, local check is whether that fixture still compiles.
- **Result**: exit 0 — clean; the only output is an unrelated node `ExperimentalWarning` about a CommonJS/ES-module `require()` in `debug`/`supports-color`.
- **What it proves**: The e2e TypeScript, including `capture.ts` and `session.ts`, compiles with zero errors — the fixture is not broken at the type level.
- **What it does NOT prove**: **The behavioural claim is entirely unexecuted.** Whether `assertClean()` skips a failing test's evidence, and whether blank/stuck states are enforced or merely reported, requires a Playwright run — deferred for this phase.
- **Revised evidence classification**: unchanged — evidence strengthened (e2e-typecheck half only); behavioural half deferred to a Playwright lane.

### 2.6 WORK family

#### WORK-03
- **Claim ID**: WORK-03 — the `chat_escalation_sends` migration and its ORM model exist in-repo; `deploy-staging.yml` runs migrations before the service switch. Only a deploy is needed to reach staging.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: the migration replay described under ARCH-08 (scratch DB create → `alembic upgrade head` → `current` → `heads` → drop), plus `uv run pytest packages/db/tests/ -q -rA` and a confirmation re-run of `test_autogenerate_never_drops_the_checkpoint_tables.py`.
- **Why relevant**: CLAUDE.md requires every migration to replay from empty, so this claim's repo half is a project rule with a command attached rather than a 3B-only fact.
- **Result**: **replay from EMPTY ran and succeeded — 37 migrations base → head, single head `8509c0486d8d`, which IS the D-421 `chat_escalation_sends` migration**; scratch DB dropped afterwards. `packages/db/tests/` exit 0 — collected 83 / passed 83 / failed 0 / skipped 0; the checkpoint-table guard re-run alone: `4 passed in 0.01s`.
- **What it proves**: The migration is real, applies from an empty database in sequence with the other 36, and leaves a single head with no branch divergence. The autogenerate guard that protects the checkpoint tables passes.
- **What it does NOT prove**: Staging's schema state — whether the migration has been applied there — is 3B. A commit is not a deploy, and `terraform apply` is not part of `deploy-staging.yml`.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (repo half)**; staging schema state remains 3B.

#### WORK-08
- **Claim ID**: WORK-08 — D-401 (alarm severity split) and D-406 (NAT follows consumers) are both fully present in config and were committed before the disputed date (15bb6b3, 73e29c6, with 2e301d6 titled "applied"), so `PROGRESS.md:155-156`'s "unblocked but unapplied" is likely stale. But a commit title is a claim of an apply, not the apply.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `uv run pytest packages/observability/tests/test_alarm_severity_routing.py …` (batch 2, same run as COST-19/23/24 and REQ-49); the D-406 map grep under ARCH-29/COST-28.
- **Why relevant**: D-401's *enforcing test* is the one part of this claim that executes, and it parses the real terraform files.
- **Result**: batch 2 exit 0, 1.0s — collected 17 / passed 17 / failed 0 / skipped 0. The D-406 map is present at `terraform/environments/staging/main.tf:115-136`.
- **What it proves**: Both decisions are present in the checked-in config, and D-401's enforcing test executes and passes against that config.
- **What it does NOT prove**: **Applied-vs-unapplied is precisely a `terraform plan`/AWS question (3B), and `terraform` is forbidden here.** The repo's own comment at `staging/main.tf:543-549` documents a config change that was never applied — so a commit title claiming an apply is not an apply.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (config half)**; the apply question remains 3B.

#### WORK-11
- **Claim ID**: WORK-11 — the D-417/C8 formatting-enforcement convention: `make lint` is read-only (`ruff format --check`, not `format`) and the formatted-file denominator is as documented.
- **Previous Phase 3A classification**: CONFIRMED (co-claim of X2 STEP 1; not part of the 62-claim extraction in `targets_3a5.md`)
- **Command executed**: `make lint` (→ `uv run ruff check .` then `uv run ruff format --check .`).
- **Why relevant**: C8's whole point is that asking the question must not rewrite the answer, so the read-only property has to be observed rather than assumed.
- **Result**: exit 0 — `All checks passed!` and **`440 files already formatted`**. No file rewritten; `git status --porcelain` unchanged.
- **What it proves**: C8's enforcement is executed-verified: lint is clean *and* read-only. The denominator moved **437 → 440**, accounted for by the three post-C8 files — internally consistent, not a drift.
- **What it does NOT prove**: That CI runs the same invocation (inferred from `.github/workflows/ci.yml` per TEST-04, not executed in CI here). `make fmt` was deliberately never invoked.
- **Revised evidence classification**: CONFIRMED → **LOCALLY_VERIFIED** — enforcement executed clean, denominator explained.

#### WORK-12
- **Claim ID**: WORK-12 — learning-web's disconnect-banner render condition is called "deliberately untested (D-417/C7)" in `App.tsx:958-960` while `PROGRESS.md:107-117` carries it as open after W21. Two live statuses, neither retracted.
- **Previous Phase 3A classification**: **CONFLICT**
- **Command executed**: `grep -rnE "banner|streamState" apps/learning-web/src --include="*.test.*"`; `ls e2e/tests/learning/ | grep -i disconnect`; `ls e2e/tests/chat/ | grep -i disconnect`; `find apps/*/src -name "*.test.*"`; `cd apps/learning-web && npm test` and `npx vitest run --reporter=verbose`; `cd apps/chat-web && npx vitest run --reporter=verbose`.
- **Why relevant**: The claim is a *negative inventory*, so the executable part is confirming what the existing tests do and do not cover, in both apps.
- **Result**: learning-web `npm test` → `4 passed (4)` files / **`26 passed (26)`** tests, covering masteryBands / stream liveness / attendanceLabels / ConnectingPanel — **none a banner test**. The single `banner|streamState` grep hit is **prose inside a test name** (`stream.test.ts:148`), not an assertion. `ls e2e/tests/learning/ | grep -i disconnect` → **exit 1, no matches**; the chat counterpart `e2e/tests/chat/stream-disconnect-visible.spec.ts` **does** exist. chat-web: **49 passed (49)** across 5 files, including six dedicated disconnect-banner / connection-dot assertions in both directions (appears on error; does not appear while connecting or open).
- **What it proves**: Execution **CONFIRMED the absence** — learning-web has no stream-disconnect visibility test at either level, so the in-code "deliberately untested (D-417/C7)" note is accurate as to state. The asymmetry is real and one-directional: chat-web is the tested app for the same user-visible failure.
- **What it does NOT prove**: **The PROGRESS-vs-code status conflict is documentary and unresolved by any command.** It needs the D-417/C7 text read and a scope decision (chat vs learning); no execution retracts either statement.
- **Revised evidence classification**: **unchanged (CONFLICT)** — the absence is now executed-confirmed; the two live statuses remain unreconciled.

#### WORK-15
- **Claim ID**: WORK-15 — D-342's parking rests on one property: every declared tier of every spanning skill is servable (driven from the real taxonomy, with its own vacuity guard).
- **Previous Phase 3A classification**: CONFIRMED (carries a TEST_EXISTS_NOT_EXECUTED limitation)
- **Command executed**: `uv run pytest apps/learning-api/tests/test_study_plan_difficulty_routing.py …` (batch 5).
- **Why relevant**: A parking decision whose premise has never been executed is an assumption. The test is driven from the real taxonomy rather than a fixture and carries a vacuity guard, so a pass is strong evidence and a fail would invalidate the parking.
- **Result**: batch 5 exit 0, 4.8s — collected 41 / passed 41 / failed 0 / skipped 0 / errors 0, including `test_every_declared_tier_of_every_spanning_skill_is_servable`, `test_an_exactly_matching_tier_still_wins_over_a_nearby_one`, `test_falls_back_to_the_whole_pool_rather_than_serving_nothing`, `test_a_fully_used_skill_still_serves_rather_than_failing`.
- **What it proves**: **D-342's load-bearing property — every declared tier servable, real taxonomy, vacuity guard — passed. The parking decision's premise is now executed-verified rather than assumed.**
- **What it does NOT prove**: The property holds for the taxonomy *as it is today*; adding a skill or tier could break it, and only re-running catches that. Nothing about served difficulty quality in production (3B).
- **Revised evidence classification**: CONFIRMED (TEST_EXISTS_NOT_EXECUTED limitation) → **limitation resolved, LOCALLY_VERIFIED**.

#### WORK-21
- **Claim ID**: WORK-21 — a 180-day chat-checkpoint retention policy is implemented (D-333, two-condition classifier so an unprojected learning thread cannot be deleted under the chat policy), but it is **not scheduled** (`grep -rn checkpoint_retention terraform/` → no matches) and is dry-run by default, so chat checkpoints remain unbounded in practice.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest apps/learning-api/tests/test_checkpoint_retention.py …` (batch 6, same run as WORK-35 / COST-10).
- **Why relevant**: Both halves of the finding — dry-run-by-default and the two-condition classifier — are behaviours the suite asserts directly, so execution settles the code half outright.
- **Result**: batch 6 exit 0, 5.2s — collected 55 / passed 55 / failed 0 / skipped 0. `test_apply_is_off_unless_explicitly_true` and `test_the_chat_classifier_requires_the_absence_of_phase_not_just_a_missing_summary` both passed, along with the all-three-tables delete and the three-decided-windows tests.
- **What it proves**: Dry-run-unless-explicit, the two-condition classifier, the three decided windows, and the three-table coverage all execute and pass — a learning thread cannot be deleted under the chat policy.
- **What it does NOT prove**: **The unscheduled-in-terraform drift STANDS unchanged** — a correct, tested purge that nothing invokes still leaves checkpoints unbounded. The "2,178 threads / 35.6 MB" figures are staging-DB facts (3B).
- **Revised evidence classification**: PARTIALLY_IMPLEMENTED → **LOCALLY_VERIFIED (code half)**; the unscheduled-in-terraform drift stands.

#### WORK-27
- **Claim ID**: WORK-27 — MEDIUM drift: the slot→role mapping is confirmed, but `.env.example:28-37` makes the Generator share with **Solver A**, not Solver B (mirror image of `QUESTION_GENERATION.md:266-271`); `curriculum/settings.py:23-33` defaults all four slots to `anthropic.claude-sonnet-5`, the id D-273 measured as AccessDenied.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `uv run pytest packages/curriculum/tests/test_authored_pipeline.py -k "solver" -q -rA` (batch 3a-ii).
- **Why relevant**: The whole argument rests on the fail-closed solver-distinctness preflight — if the pigeonhole guard does not actually refuse, the roster question is moot because nothing would catch a collapse.
- **Result**: exit 0, 2.3s — collected 90 / selected 10 (80 deselected) / passed 10 / failed 0 / skipped 0, including `test_preflight_fails_when_the_two_solvers_are_one_model` and `test_two_inference_profiles_for_one_model_are_not_two_solvers`.
- **What it proves**: The pigeonhole preflight guard executes and refuses correctly, including the subtle case where two inference profiles wrap one model.
- **What it does NOT prove**: The **operative** roster — `.env` is forbidden to read (only `.env.example` shape), and model invocability is a live AWS account fact. No paid target was invoked.
- **Revised evidence classification**: unchanged — evidence strengthened (preflight guard executed); the MEDIUM roster drift stands and the operative roster remains unreadable by instruction.

#### WORK-35
- **Claim ID**: WORK-35 — OPEN_DECISIONS #4 option D confirmed: `session-consolidate` is in the same `locals.jobs` map as `retention-purge`, enabled and ordered first (D-356), reusing `packages/memory`'s already-scheduled entrypoint; `checkpoint_retention_cli` is deliberately **not** in `locals.jobs`.
- **Previous Phase 3A classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Command executed**: `uv run pytest apps/learning-api/tests/test_session_consolidation.py apps/learning-api/tests/test_consolidation_scheduler.py packages/memory/tests/test_consolidation.py …` (batch 6, same run as WORK-21 / COST-10).
- **Why relevant**: Idempotency is the property that makes a nightly job safe to schedule at all, and it is only observable by running it twice — which the suite does.
- **Result**: batch 6 exit 0, 5.2s — collected 55 / passed 55 / failed 0 / skipped 0 (consolidation + scheduler + memory suites).
- **What it proves**: The consolidation logic, its scheduler wiring, and the memory-package entrypoint all execute and pass, including the idempotency assertions.
- **What it does NOT prove**: The claimed operational numbers (36,929 rows, 0 on a second run, 40 s vs 4m00s) are staging facts, and criterion 6's ≥1-week unattended clock is a live-schedule fact — both 3B.
- **Revised evidence classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → **LOCALLY_VERIFIED (code half)**; the schedule's firing record remains 3B.

#### WORK-37
- **Claim ID**: WORK-37 — the sync-preflight guard that pins the computation behind the 2026-08-15 staging incident in which 182 videos were marked inactive.
- **Previous Phase 3A classification**: CONFIRMED (cited tests unexecuted)
- **Command executed**: `uv run pytest packages/youtube/tests/test_sync_preflight.py packages/youtube/tests/test_catalog_sync.py …` (batch 5).
- **Why relevant**: The test deliberately targets the *computation* rather than the flag's effect, because the old tests passed the flag in — so a pass here is evidence about the incident's actual cause.
- **Result**: batch 5 exit 0, 4.8s — collected 41 / passed 41 / failed 0 / skipped 0 / errors 0. The guard is at `packages/youtube/tests/test_sync_preflight.py:157` (docstring cites "182 videos"), with `assert saw_whole_channel(covered=72, deferred=0) is False` at `:166`; `test_a_resumable_run_that_skipped_covered_skills_must_not_deactivate`, `test_a_quota_capped_run_must_not_deactivate`, and `test_only_a_run_that_searched_every_skill_may_deactivate` all executed and passed.
- **What it proves**: **The `saw_whole_channel(covered=72, deferred=0) is False` guard passed** — a partial run cannot authorise a deactivation sweep, which is exactly the computation that failed on 2026-08-15.
- **What it does NOT prove**: That the 182 rows were actually restored in staging, or that a real YouTube quota cap produces the same inputs (3B / external API).
- **Revised evidence classification**: CONFIRMED → **strengthened, LOCALLY_VERIFIED** — the incident-guard computation is executed-verified.

#### WORK-40
- **Claim ID**: WORK-40 — items 1–2 built (`stage_narrative_stage` on five response models + the ladder-pause breadcrumb sink). Item 3: no `formatDateLabel` symbol exists; the real formatter is `buildDateLabelFormatter(timeZone)` using the server-supplied `org_time_zone` with a deliberate UTC fallback, but the date-only back-a-day shift is undefended.
- **Previous Phase 3A classification**: PARTIALLY_IMPLEMENTED
- **Command executed**: `cd apps/learning-web && npm run build && npm test`; `grep -rn "formatDateLabel\|buildDateLabelFormatter" apps/learning-web/src apps/chat-web/src`; `grep -n "export function buildDateLabelFormatter" …`; `grep -rn "toLocaleDateString\|toLocaleString\|Intl.DateTimeFormat" apps/chat-web/src apps/learning-web/src`; `cd apps/chat-web && npm run build && npx vitest run`.
- **Why relevant**: The symbol-absence and export halves are grep/build questions; the formatter's *coverage* is answerable by inventorying which tests touch it.
- **Result**: learning-web build exit 0 (`644 modules transformed`, `built in 295ms`, one >500 kB chunk warning); tests `26 passed (26)`. `formatDateLabel` does not exist; `buildDateLabelFormatter` appears only at `StudentDashboardScreen.tsx:79,220,427`, and `grep -n "export function buildDateLabelFormatter"` → **exit 1, not exported** (module-private, therefore not unit-testable as written). Its only coverage is a Playwright spec (`e2e/tests/learning/dashboard-chart-labels.spec.ts`), i.e. the deferred lane. chat-web build exit 0 (`39 modules transformed`, `built in 185ms`), `49 passed (49)`.
- **What it proves**: Items 1–2 compile and ship; the item-3 symbol claim is corrected (the formatter exists under a different name, is module-private, and has zero unit coverage). **NEW IMPLEMENTATION FINDING (MEDIUM): `apps/chat-web/src/screens/CalendarActionModal.tsx:12-15` `formatDateTime` calls `date.toLocaleString()` with no `timeZone`/locale argument** — the same viewer-locale defect class D-324 fixed in learning-web, whose fix (`buildDateLabelFormatter(timeZone)`) is module-private and covered only by the deferred Playwright lane. Calendar-approval times therefore render in the viewer's browser zone, not org time. **NOT FIXED (audit); recorded only.**
- **What it does NOT prove**: The three breadcrumb specs are Playwright and were deferred. Whether any endpoint returns a date-only field — which would arm the back-a-day shift — was not traced and needs a fresh read, not a command.
- **Revised evidence classification**: unchanged — **NEW MEDIUM implementation finding recorded** (chat-web `CalendarActionModal` viewer-locale defect); the build/symbol halves confirmed by executed commands.

---

## 3. Commands intentionally not run

Each of these was available and was deliberately skipped. The reason is recorded so that a later
phase does not mistake a deferral for a gap in coverage — and so that no result here is read as
covering them.

1. **Playwright e2e** — the 5 TEST-22 specs, TEST-27's behavioural half, WORK-40's three breadcrumb
   specs, and WORK-12's banner spec. Playwright **shares the dev Postgres with pytest** and needs
   both APIs plus both Vite servers running; deferred by phase design. The command would be
   `make e2e`.
2. **Whole-suite `make test`** — the targeted batches answered every claim; a blanket run adds no
   claim-level evidence (user instruction).
3. **All AWS-credentialed `make` targets** — `scan-traces`, `scan-logs`, `scheduler-evidence`,
   `scaling-evidence`, `image-check`, `profile-span`, `e2e-staging`, `load-staging-chat`,
   `load-staging-learning`, `security-scan-staging`. Every one needs live AWS → Phase 3B.
4. **Paid targets** — `question-gen-run`, `question-gen-authored`, and `scripts/measure_*`. These
   spend real money and are out of scope for a verification phase.
5. **`scripts/scan_logs_pii.py`** — reads staging CloudWatch → Phase 3B. (It is TEST-02's 14th cited
   artifact, and the one that could not be converted from existence to evidence here.)
6. **New-test authoring** — SEC-13's cancel-path proof, COST-06's flush-time `IntegrityError`
   branch, and REQ-27's fail-closed empty-frozenset behaviour. Writing new test code exceeds
   "repository-defined validation commands" in an audit. All three are recorded as the **three
   highest-value new-test candidates for post-audit work**; none needs a paid or live dependency
   (the dev Postgres and the fake gateway suffice).
7. **`terraform plan` / `apply` / `init`** — forbidden: they read or mutate live state.

---

## 4. Classification movement summary

### 4.1 Per-claim movement

| Claim | Phase 3A classification | Phase 3A.5 revised |
|---|---|---|
| REQ-10 | PARTIALLY_IMPLEMENTED | unchanged — evidence strengthened |
| REQ-12 | CONFIRMED | unchanged — evidence strengthened |
| REQ-17 | PARTIALLY_IMPLEMENTED | unchanged — wording corrected: "declared, never used" |
| REQ-19 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (repo half — six gateway features) |
| REQ-20 | TEST_EXISTS_NOT_EXECUTED | → LOCALLY_VERIFIED (repo half) |
| REQ-27 | PARTIALLY_IMPLEMENTED | **SPLIT**: no-notice half → LOCALLY_VERIFIED; fail-closed frozenset unexecuted |
| REQ-28 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (code half) |
| REQ-32 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (single-test, thin) |
| REQ-39 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (repo half); MEDIUM UI-wording drift stands |
| REQ-40 | TEST_EXISTS_NOT_EXECUTED | → LOCALLY_VERIFIED (repo half) |
| REQ-44 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (weak — vacuity caveat) |
| REQ-49 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (routing half); two absences re-confirmed |
| REQ-51 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (repo half) |
| REQ-52 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (repo half) |
| ARCH-01 | PARTIALLY_IMPLEMENTED | unchanged — split verdict: decisions current, provenance stale (16/48) |
| ARCH-02 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (config half) |
| ARCH-03 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (repo half) |
| ARCH-08 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (migration half) |
| ARCH-12 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (config half) |
| ARCH-29 | PARTIALLY_IMPLEMENTED | unchanged — evidence strengthened |
| ARCH-30 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (masking half) |
| ARCH-33 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (repo half) |
| ARCH-35 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (config half) |
| SEC-04 | PARTIALLY_IMPLEMENTED | unchanged — evidence strengthened |
| SEC-05 | CONFIRMED | unchanged — evidence strengthened |
| SEC-06 | CONFIRMED | unchanged — evidence strengthened |
| SEC-10 | PARTIALLY_IMPLEMENTED | unchanged — wording corrected: 4 lines, not 3 |
| SEC-12 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (code half) |
| SEC-13 | PARTIALLY_IMPLEMENTED | unchanged — evidence strengthened (zero test files confirmed) |
| SEC-23 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (masking half) |
| SEC-25 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (gate logic) |
| COST-03 | CONFIRMED | → LOCALLY_VERIFIED (with REQ-19, 44/44) |
| COST-06 | **CONFLICT** | **unchanged (CONFLICT)** |
| COST-10 | PARTIALLY_IMPLEMENTED | unchanged — **SHARPENED** (MEDIUM stands) |
| COST-13 | CONFIRMED | unchanged — evidence strengthened |
| COST-16 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (settings-declaration half) |
| COST-17 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (reporting half) |
| COST-19 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (config-parsing half) |
| COST-23 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (config-parsing half) |
| COST-24 | CONFIRMED | → LOCALLY_VERIFIED (config-parsing half) |
| COST-27 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (masking half) |
| COST-28 | CONFIGURED_NOT_RUNTIME_VERIFIED | unchanged — evidence strengthened |
| COST-29 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (config half) |
| TEST-02 | PARTIALLY_IMPLEMENTED | → **LOCALLY_VERIFIED (repo half)** — largest single conversion |
| TEST-04 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (mechanism half); 41-vs-31 confirmed |
| TEST-09 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (repo half) |
| TEST-12 | CONFIRMED (TEST_EXISTS_NOT_EXECUTED limitation) | → LOCALLY_VERIFIED (ran, not skipped) |
| TEST-13 | CONFIRMED | unchanged — location corrected; tests found and passed |
| TEST-14 | TEST_EXISTS_NOT_EXECUTED | → LOCALLY_VERIFIED |
| TEST-22 | TEST_EXISTS_NOT_EXECUTED | **SPLIT**: 6 pytest → LOCALLY_VERIFIED; 5 Playwright specs remain TEST_EXISTS_NOT_EXECUTED |
| TEST-23 | TEST_EXISTS_NOT_EXECUTED | → LOCALLY_VERIFIED (both API halves); browser half deferred |
| TEST-27 | PARTIALLY_IMPLEMENTED | unchanged — evidence strengthened (e2e-typecheck half only) |
| WORK-03 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (repo half) |
| WORK-08 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (config half) |
| WORK-11 | CONFIRMED | → LOCALLY_VERIFIED |
| WORK-12 | **CONFLICT** | **unchanged (CONFLICT)** — absence executed-confirmed |
| WORK-15 | CONFIRMED (TEST_EXISTS_NOT_EXECUTED limitation) | → LOCALLY_VERIFIED (limitation resolved) |
| WORK-21 | PARTIALLY_IMPLEMENTED | → LOCALLY_VERIFIED (code half); unscheduled drift stands |
| WORK-27 | PARTIALLY_IMPLEMENTED | unchanged — evidence strengthened |
| WORK-35 | CONFIGURED_NOT_RUNTIME_VERIFIED | → LOCALLY_VERIFIED (code half) |
| WORK-37 | CONFIRMED | → LOCALLY_VERIFIED |
| WORK-40 | PARTIALLY_IMPLEMENTED | unchanged — NEW MEDIUM implementation finding recorded |

### 4.2 Counts

| Bucket | Count |
|---|---|
| Claims with at least one command executed for them (blocks in §2) | **62** |
| **TEST_EXISTS_NOT_EXECUTED resolved** | **5 of 5** at the pytest level — REQ-20, REQ-40, TEST-14, TEST-23, and TEST-22 (split). **Residue: TEST-22's 5 Playwright specs remain TEST_EXISTS_NOT_EXECUTED.** |
| Claims that gained LOCALLY_VERIFIED for a repo / config / code half | **43** (of which **2 are SPLITs**: TEST-22, REQ-27) |
| Claims unchanged, evidence strengthened | **11** — REQ-10, REQ-12, SEC-04, SEC-05, SEC-06, SEC-13, COST-13, COST-28, ARCH-29, WORK-27, TEST-27 |
| Claims unchanged as **CONFLICT** | **2** — COST-06, WORK-12 |
| Claims unchanged with a 3A wording correction or a new/sharpened finding | **6** — REQ-17, SEC-10, ARCH-01, TEST-13 (corrections, LOW); COST-10 (sharpened, MEDIUM stands); WORK-40 (new MEDIUM implementation finding) |
| Claims whose classification *worsened* | **0** |

**Systemic note carried forward to Phase 3B framing.** `terraform apply` is **not** part of
`deploy-staging.yml`. The repository's own comment at `terraform/environments/staging/main.tf:543-549`
records a config change that "was never applied … live stayed at the module default the whole time".
Every terraform-derived number in Phase 3A and 3A.5 — alarm routing, NAT, task sizing, schedules,
budgets — is **file state**. Phase 3B must not assume config == live.
