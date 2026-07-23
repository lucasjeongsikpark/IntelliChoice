# Expansion Plan — LLM Question Bank, Assessment UX, Tutoring Chat, Memory, Dashboards, and Real Chat Content

Date: 2026-07-18 · Status: **accepted — merged into ROADMAP.md as sessions S17–S28 (D-049)**
Covers the 2026-07-18 feature request: Learning app items 1.1–1.8 and Chat app items 2.1–2.5.
[ROADMAP.md](../ROADMAP.md) is the source of truth for session scope and order; this file is
the design reference the sessions point back into. Task-id → session map:
X1+C1=S17, C2=S18, C3=S19, L1=S20, L2=S21, L3=S22, L4=S23, L5=S24, L6=S25 (old-S17 Memory),
L7=S26, L8=S27, L9=S28. Former S18–S23 (multimodal/eval/observability/launch) are now
S29–S34 — full mapping in DECISIONS.md D-049.

---

## 1. Current-state assessment

Everything below was verified against the code on 2026-07-18 (post-S16, 261/262 tests green,
1 known-red pre-existing S9 test per PROGRESS.md).

### 1.1 Question generation (request §1.1)

**Exists.** A two-layer system:

- Deterministic shape registry: `packages/curriculum/src/intellichoice_curriculum/templates/registry.py`
  holds ~10 registered equation "shapes" (sample/render/solve triples) for `linear_equations`
  only; `generation.py::generate_variant` renders seeded variants; `validation.py::validate_variant`
  runs the §5.8.5 executable suite (unique options, exactly-one-correct, no div-by-zero, range,
  wording, leakage, dedup, difficulty rubric, alignment, age-appropriate wordlist).
- S9 LLM pipeline: `ai_pipeline.py::generate_candidate` — the Generator Agent only *picks a
  shape key* from `DIFFICULTY_SHAPES` (D-015/D-026 allowlist); the question text is still
  rendered by deterministic code. Solver A/B agreement, difficulty/ambiguity/alignment
  reviewers, dedup, then `validation_status="pending"` (human activation via
  `QuestionRepository.activate_template`, D-026). Quarantine via 5-distinct-user reports
  (D-027, `services/question_reports.py`).

**Gap.** No free-text/authored questions at all: no scenarios, tables, diagrams, or word
problems; no topics beyond `linear_equations` (`fraction_operations`/`place_value` raise
`PipelineConfigError` by design); no stored canonical hint/solution per question; no
embedding-based near-duplicate detection (dedup is exact `rendered_question` match); no
pipeline-run audit trail beyond `review_model_versions` JSON; no review tooling (activation
is a REPL call).

### 1.2 Assessment/problem-solving UX (request §1.2)

**Exists.** `apps/learning-web/src/screens/ExamScreen.tsx` — one question at a time, phase
chip, "position" string, streak counter; `useLearningSession.ts` drives 9 REST actions +
SSE; refresh-restore works (D-032 snapshot). `response_time_ms` is captured per answer.
Assessment items are created up front (`assessment_items`, fixed set, §5.9.2) but served
and graded strictly sequentially by `services/flow.py`; study phase is serve-one-at-a-time
by design (D-028 retry ladder — navigation does not apply there).

**Gap.** No timer/elapsed display, no per-question time display, no difficulty display, no
navigation bar, no skip/return/flag/review, no submit confirmation, no per-stage policy
(the exam UI currently reveals correctness mid-exam via the streak counter — arguably a
policy bug), no keyboard navigation or a11y pass. Grading happens immediately per item
(`AssessmentAttempt` written on submit with idempotency key), which conflicts with
"change an answer before final submission."

### 1.3 Hints and solutions (request §1.3)

**Exists.** `services/tutor.py` — single Bedrock `TUTOR` call for hint or solution with
deterministic fallback; solution `final_answer` cross-checked against the real correct
answer (D-023 pattern). `topic_resolver.py` builds `TutorContext` (grade, topic, skill,
question, selected wrong answer, estimated level). Intervention is a one-shot
`interrupt()` choice (`intervention_choice` node), recorded as booleans
(`StudyAttempt.hint_used/solution_used/video_used`).

**Gap.** No canonical hint/solution stored in the question bank; no progressive-disclosure
ladder (one hint shape, one level); no hint history, misconception tag, or previous
attempts on the Bedrock wire (D-023 deliberately restricts the payload to §5.30.1's exact
list — widening it is flagged there as a spec-level decision); no per-(student, question)
assistance accounting beyond the booleans; `relevant_learning_fact` slot exists but is
always `None` (S17 memory not built).

### 1.4 Khan Academy videos (request §1.4)

**Exists.** `youtube_videos` table (S15) with most §5.18.2 metadata + pgvector embedding;
`packages/youtube` sync worker (`catalog_sync.py`, `make youtube-sync`) with LLM
classification re-validated against the curriculum registry (D-046); inactive marking
(never delete); `learning_api/services/video_catalog.py::search_video` does
metadata-filter-then-cosine-rank with the §5.11.6 fallback message; zero live YouTube
calls at learning time.

**Gap.** Only `FakeYoutubeProvider` (4 stub videos) — no real YouTube Data API client, and
nothing pins the catalog to the official Khan Academy channel ID; missing metadata:
transcript/transcript segments, prerequisite skills, last-verified date, suitability
status, licensing fields; no availability re-verification job; recommendation input is
skill+difficulty only (no misconception, grade band, or mastery state); no schedule
(manual trigger, deliberate S15 scope cut).

### 1.5 Stage introductions/transitions (request §1.5)

**Does not exist.** `LearningState.last_message` carries fixed strings (attendance
messages, §5.11.6 fallback, etc.). No personalized narrative anywhere; the frontend
transitions between phases with no explanation.

### 1.6 Contextual learning chat (request §1.6)

**Does not exist.** The only assistance surface is the 3-way `intervention_choice`
interrupt on a wrong study answer. There is no chat endpoint, no multi-turn state, no
message table in learning-api. The Bedrock gateway has `generate_structured` and
`create_embedding` only — no streaming method (D-022, PROGRESS S11 carry-over). chat-api's
scope-guard/graph pattern (S13) is the closest prior art.

### 1.7 Student memory (request §1.7)

**Schema exists, nothing writes it.** `packages/db/models/memory.py` has `learning_events`
(§5.15.2) and `semantic_memory` (§5.15.3, with `evidence_event_ids`, `confidence`,
`expires_at`, `status`); `MemoryRepository` has round-trip coverage. No event emission
from any graph node, no consolidation worker, no reader. This is ROADMAP S17, already the
"next session."

### 1.8 Dashboard and report (request §1.8)

**Exists minimally.** `ParentDashboardScreen.tsx` renders `services/history.py`'s
`StudentHistory` (completed cycles from `LearningGain`, blocked weeks, reports, mastery
table — skill *names* only, D-034 fix); `ResultsScreen.tsx` shows one cycle's gain numbers.
No charts, no date filtering, no student-facing dashboard, no generated report, no
tutor/branch-manager views (§5.14.4 unbuilt).

### 2.1 Anonymous/role-gated chat access (request §2.1)

**Exists at the enforcement layer.** Anonymous access is first-class (D-040);
`role_access_filter` (D-039) applies audience/branch/date filters *before* retrieval;
role gating proven by S13 tests. **Gap:** a public user asking a tutor-only question gets
the generic fail-closed no-answer/escalation message — nothing detects "an answer exists
but requires a different role" or guides the user to log in.

### 2.2 Question coverage (request §2.2)

**Root causes are already known, documented in PROGRESS (S13/S16 carry-overs):**

1. **Every one of the 22 seeded documents has `effective_from: 2026-08-01`** (future), so
   the §5.21.3 date filter correctly excludes *all* content today — every document_qa and
   calendar query fails closed. This is the dominant cause of "doesn't answer anything."
2. All content is synthetic placeholder prose with DRAFT banners (S12), so even after the
   date gate opens, answers would be fake.
3. Dev runs `MockBedrockProvider` — scope/intent classification, reranking, and synthesis
   are deterministic stand-ins; real answer quality is unverified (D-025/D-035 caveats).
4. Single-turn only: `standalone_query` ≡ `query` (no history contextualization).
5. No capability discovery: no welcome message, suggested questions, category buttons, or
   follow-up suggestions (`ChatScreen.tsx` opens on an empty composer).
6. `clarification` intent returns one fixed message; no clarifying-question loop.
7. No retrieval diagnostics surface (what was retrieved/filtered/why is only visible in
   tests).

### 2.3 / 2.4 / 2.5 Branch, team, events, about content (request §2.3–2.5)

**All placeholder.** `knowledge-content/documents/public/branch-directory`,
`academic-calendar`, `organization-overview` etc. are synthetic (S12). Branch data for the
locator comes from `mongo_fixtures.py` (`BranchInfo` with fake addresses/coords). Calendar
answers are LLM-extracted from RAG chunks per turn (`calendar_extract`, D-038-style
re-derivation) — there is no structured events table, no recurrence/status model, no
distinction between upcoming/past events beyond what the chunk text says. Ingestion
(`packages/knowledge`, S12) is manifest-driven, idempotent by `source_sha256`, and already
supports versioning fields — the pipeline is reusable; the *content* and a web-extraction
step are what's missing. No welcome message exists (see 2.2).

---

## 2. Proposed architecture

Ten guiding calls, consistent with the codebase's established decisions:

1. **Authored questions extend the existing bank; delivery paths don't change.**
   `question_templates` gains an `authoring_mode` discriminator (`"shape"` | `"authored"`)
   plus nullable authored-content columns. Authored items get exactly one static
   `QuestionVariant` (the rendered form), so `assessment_builder.build_pre_exam`,
   `study_plan.py`, grading, quarantine, and the §5.8.6 selection query keep working
   unmodified. Variety for authored items comes from generating many items per skill, not
   from seeded re-rendering.
2. **Validation stays "deterministic gate → LLM reviewers → human activation"** — the
   D-026 lifecycle (`pending` → human-approved) is kept verbatim and extended, never
   bypassed. New: SymPy independent solving where machine-checkable, embedding
   near-duplicate detection, canonical hint/solution consistency checks, and a persisted
   per-run audit record (`question_validation_runs`).
3. **Canonical hint ladder + worked solution live in the bank** (per template), produced
   and validated by the same pipeline. Runtime personalization (1.3) is a rewrite of
   approved canonical content with the stored answer as immutable ground truth — the
   existing `final_answer` cross-check pattern (tutor.py:135) generalizes to every level.
4. **Exams get a per-session-type `AssessmentPolicy`** (deterministic config, procedural
   memory in the §5.15.1 sense): timing, navigation, review, hint availability, feedback
   visibility. Pre/post exams move to save-answers-then-finalize grading; study keeps
   grade-on-submit + retry ladder (D-028) untouched.
5. **Learning chat is a new bounded LangGraph node cluster inside learning-api**, reusing
   chat-api's scope-guard pattern, with deterministic intent shortcuts (hint / solution /
   video / explain-why-wrong) that call the *existing* services rather than letting the
   model freestyle. Transcripts are short-retention rows (`tutor_chat_messages`), never
   long-term memory (1.7 consolidates them instead).
6. **Memory follows SPEC §5.15.4 exactly** (episodic events → PII minimization →
   summarizer → deterministic validation → upsert), triggered per completed
   session *and* weekly, manual CLI trigger in dev (same posture as `youtube-sync`).
7. **Chat-app content becomes real via an offline extraction pipeline**, not runtime
   fetching: a new `packages/webcontent` CLI fetches the four intellichoice.org URLs,
   emits reviewed Markdown + manifests into `knowledge-content/` *and* structured records
   (branches, team, events) into Postgres seed files. Humans review the diff before
   `make knowledge-load` — same "approved content only" posture as everything else.
8. **Events get a structured `org_events` table** and the calendar intent queries it
   deterministically first, with the existing RAG-extraction path as fallback — removes a
   per-turn LLM extraction for known events and makes upcoming/past/canceled a code
   decision, not prose interpretation.
9. **Access-aware refusals are computed in the query layer:** when role-filtered retrieval
   is empty, a second metadata-only probe (counts + audiences, content never leaves the
   repository layer) determines whether higher-audience chunks match; if so the response
   is a deterministic "this requires X login" message. The LLM never decides access.
10. **All new LLM calls go through the existing `ResilientBedrockGateway`** with new
    `BedrockTask` members, strict `extra="forbid"` payloads, Pydantic-validated responses,
    deterministic fallbacks, and per-session cost budgets — no new call path.

---

## 3. Database and schema changes

All in `packages/db` (D-009), one Alembic migration per session, replayable from empty,
PII-purity test (`test_schema_purity.py`) must keep passing — every new table is
external-id-only.

### New columns on existing tables

| Table | New columns | For |
|---|---|---|
| `question_templates` | `authoring_mode` (default `"shape"`), `stem_markdown`, `context_block` (JSON: scenario text / table rows / labeled values), `answer_expression` (SymPy-parseable, nullable), `canonical_hints` (JSON: ordered ladder, levels 1–3), `canonical_solution` (JSON: steps + final answer), `stem_embedding` (Vector, nullable), `review_priority` (nullable), `generation_run_id` (nullable FK) | 1.1, 1.3 |
| `assessment_sessions` | `topic_id` (FK, currently only discoverable via items), `policy` (JSON snapshot of the AssessmentPolicy applied), `time_limit_seconds` (nullable), `finalized_at` (nullable) | 1.2 |
| `assessment_attempts` | *(unchanged — becomes the finalize-time grading record)* | 1.2 |
| `youtube_videos` | `prerequisite_skill_ids` (JSON), `transcript_available` (bool), `transcript_language`, `license`, `last_verified_at`, `suitability_status` (default `"approved"`), `verification_failures` (int) | 1.4 |
| `semantic_memory` | `superseded_by_id` (nullable self-FK), `contradicts_event_count` (int, default 0) | 1.7 |

### New tables

| Table | Key fields | For |
|---|---|---|
| `question_validation_runs` | run_id, question_template_id FK, pipeline_version, stage results (JSON: per-check pass/fail + reviewer scores + model ids), solver_agreement, cost_cents, created_at | 1.1 auditability |
| `assessment_item_state` | assessment_item_id FK (unique), saved_option (nullable), status (`unseen/answered/skipped/flagged`), first_viewed_at, time_spent_ms (accumulated), updated_at | 1.2 nav/skip/flag/autosave |
| `hint_events` | id, student_external_id, study_attempt_id FK nullable, question_variant_id FK, source (`intervention/chat`), hint_level (1–4), content_hash, created_at | 1.3 progressive disclosure + 1.7 evidence |
| `tutor_chat_messages` | id, student_external_id, learning_session_id, question_variant_id FK nullable, role (`student/tutor`), content, resolved_intent (nullable), created_at — **90-day retention target (§5.15.2)** | 1.6 |
| `stage_transitions` | id, student_external_id, learning_session_id, stage (`pre_intro/pre_outro/study_step/study_outro/post_outro`), narrative_text, evidence (JSON of the numbers/names injected), generated (bool — false when fallback template used), created_at | 1.5 |
| `student_reports` | id, student_external_id, audience (`student/parent/tutor/branch_manager`), date_range, facts (JSON), interpretations (JSON), recommendations (JSON), generated_at | 1.8 |
| `video_transcript_segments` (phase 2, optional) | youtube_video_id FK, start_seconds, end_seconds, text, embedding | 1.4 timestamps |
| `org_branches` | branch_external_id (natural key), name, address, phone, email, hours (JSON), latitude/longitude, source_url, content_hash, last_verified_at, status | 2.3 |
| `org_team_members` | id (slug), name, role_title, biography, branch_external_id nullable, audience (default public), source_url, content_hash, last_verified_at, status — *staff names published on the org's own public website are public content, not student PII; confirm this reading before building (see §19)* | 2.3 |
| `org_events` | id (slug), title, description, starts_at, ends_at, timezone, location, audience, branch_external_id nullable, registration_url, recurrence_rule (nullable RFC 5545 RRULE), status (`upcoming/completed/changed/canceled`), source_url, content_hash, last_verified_at | 2.4 |
| `chat_suggestions` | id, role_audience, category, prompt_text, sort_order, active | 2.2/2.5 |

Repositories: one new repository per table in `packages/db/src/intellichoice_db/repositories/`
(existing convention: ~1 round-trip test each in `test_repositories.py`).

**Explicitly not stored:** raw student free-text is only in `tutor_chat_messages`
(short retention); no transcript text in `semantic_memory` (evidence is event IDs);
no location, names, or emails anywhere new (schema-purity denylist still applies).

---

## 4. API and DTO changes

### learning-api (`apps/learning-api/src/learning_api/routers/`)

Existing surface (kept): `POST /learning/sessions`, `/student`, `/topics`,
`/attendance-resolution`, `/answers`, `/respond`, `/resume`, `GET /stream`,
`GET /learning/students/{id}/sessions`, `POST /learning/questions/{id}/reports`.

New/changed:

| Route | Change | For |
|---|---|---|
| `POST .../answers` | Behavior split by phase: study/post unchanged; pre/post exam mode governed by policy (see next rows) | 1.2 |
| `PUT .../exam/items/{item_id}/answer` | Save (not grade) an option for an exam item; upserts `assessment_item_state`; idempotent | 1.2 |
| `POST .../exam/items/{item_id}/skip` / `/flag` | Mark status | 1.2 |
| `POST .../exam/finalize` | Grades every saved answer into `assessment_attempts`, closes the session, advances the graph (`entry_action="finalize_exam"`); confirmation payload lists unanswered items | 1.2 |
| `GET .../exam/overview` | Item statuses + per-item time + difficulty labels + remaining time (policy-gated fields) | 1.2 |
| `POST .../chat/messages` | Tutor chat turn for the active question; response = reply + optional attached intervention (hint/solution/video card) | 1.6 |
| `GET .../chat/messages` | Current session transcript (bounded) | 1.6 |
| `GET /learning/students/{id}/dashboard?range=` | Aggregates for the dashboard (mastery by skill, accuracy trend, time, hint usage, difficulty progression) | 1.8 |
| `POST /learning/students/{id}/reports` | Generate + persist a `student_reports` row; `GET .../reports/{id}` fetches | 1.8 |
| `SessionSnapshotEvent` | + `stage_narrative`, `exam_overview` (compact), `assistance_summary` (hint level used per current question) | 1.2/1.5 |

DTO rules unchanged: explicit Pydantic models per boundary, skill *names* only outward
(D-034 #4), snapshot shape stays a superset of action responses (D-032).

### chat-api (`apps/chat-api/src/chat_api/`)

| Route | Change | For |
|---|---|---|
| `GET /chat/meta` | New, anonymous-OK: welcome text (sourced from the ingested about document), suggested prompts for the caller's resolved role (`chat_suggestions`), capability summary | 2.2/2.5 |
| `POST .../messages` | Response gains `access_hint` (nullable: `{required_role, message}`) and `suggested_followups: list[str]` | 2.1/2.2 |
| `GET /chat/events?window=` | Optional, deterministic upcoming-events listing straight from `org_events` (public audience filter) — lets the UI show a calendar card without a model call | 2.4 |

`apps/*/src/*/types.ts` mirrors updated by hand (existing convention, types.ts:1).

---

## 5. LangGraph changes

### learning-api graph (`graph/build.py`, `nodes.py`, `state.py`)

- **`LearningState` additions:** `exam_deadline_at: str | None`, `stage_narrative: str | None`,
  `chat_turn_count: int = 0`, `assistance_level_by_variant: dict[str, int]` (hint ladder
  position per question), plus `entry_action` values `save_exam_answer` (thin — may bypass
  the graph, see below), `finalize_exam`, `chat_message`.
- **New nodes:**
  - `finalize_exam` — grades saved answers via `flow.py`, computes score/weak skills (pre)
    or learning gain (post), then routes into `stage_narrative`.
  - `stage_narrative` — assembles deterministic evidence (scores, weak-skill *names*, gain
    numbers, next-step decided by the planner), one Bedrock `STAGE_NARRATIVE` call,
    deterministic template fallback (1.5). Runs after pre-exam finalize, study completion,
    and post-exam finalize; a cheap static variant at stage *entry* (no LLM needed to say
    "you're starting the pre-exam and here's why").
  - `tutor_chat` — scope guard (reuses the SCOPE_AND_INTENT pattern with a
    learning-specific intent set: `question_help / request_hint / request_solution /
    request_video / why_wrong / off_topic`), deterministic dispatch of the four intents to
    the existing `tutor.generate_hint`, `generate_solution`, `video_catalog.search_video`,
    and a new `explain_why_wrong` prompt; free chat replies via a new `TUTOR_CHAT` task.
    Per-stage gate: node refuses during pre/post exam unless policy allows (fail closed).
  - `emit_events` — not a node: a small helper called from existing node bodies
    (`submit_answer`, `intervention_choice`, `finalize_exam`, `tutor_chat`) that writes
    `learning_events` rows (S17 "backfill emit points" exactly as ROADMAP anticipated).
- **Design choice:** exam answer *saving* (`PUT .../answer`) is a plain repository write,
  **not** a graph turn — it's high-frequency, has no routing consequence, and keeping it
  out of `ainvoke` avoids checkpoint churn. The graph only sees `finalize_exam`. This
  mirrors how `GET /stream` reads state without invoking. (D-021's 409-pause-guard still
  applies to `finalize_exam`.)

### chat-api graph

- `answer_document_qa` gains a post-retrieval branch: empty role-filtered retrieval →
  `access_probe` (deterministic repository call, §2 item 9) → either the existing
  no-answer/escalation message or a role-guidance answer with `access_hint` set. New node
  or inline in the existing node — recommend a separate `explain_access` node so the
  routing is testable in `test_qa_graph.py` style.
- `calendar_extract` is re-pointed: query `org_events` first (deterministic date logic:
  status + `starts_at` vs now → current/upcoming/historical phrasing); fall back to the
  existing RAG-extraction path only when no structured event matches. `calendar_action`
  (interrupt + `.ics`) unchanged.
- Optional (carry-over-sized): `standalone_query` rewrite node for multi-turn
  contextualization — flagged as its own small task, not bundled.

---

## 6. LLM integration strategy

All via `ResilientBedrockGateway` (timeouts, bounded retry, circuit breaker, cost budget,
model registry per task — §5.25). New `BedrockTask` members and payloads in
`packages/shared/src/intellichoice_shared/bedrock.py`, each `extra="forbid"` with the
narrowest field list (D-023's rule), each with a `MockBedrockProvider` deterministic branch:

| Task | Payload → Response | Fallback |
|---|---|---|
| `AUTHORED_QUESTION_GENERATION` | curriculum context, difficulty rubric, format spec → full authored item incl. canonical hints/solution | none — pipeline is offline; failed call = rejected candidate |
| `QUESTION_JUDGE` (reused for ambiguity/difficulty/alignment/safety reviews of authored items; distinct model from the generator per §5.31/§5.25.2) | item → per-dimension scores + rationale | reject candidate (fail closed) |
| `HINT_PERSONALIZATION` | canonical hint level content, question, wrong answer, misconception tag, attempt count, hint level, `relevant_learning_fact` → rewritten hint | serve the canonical hint verbatim |
| `TUTOR_CHAT` | question, options, student message (see privacy §15), canonical solution summary, assistance level, stage policy → reply + `suggested_action` | fixed "let's look at a hint" reply routing to the deterministic ladder |
| `STAGE_NARRATIVE` | stage, evidence numbers/names (code-injected) → 2–4 sentence narrative | deterministic template with the same slots |
| `MEMORY_CONSOLIDATION` | week's event summaries (minimized), existing facts → `MemoryUpdate` (§5.15.4 schema) | no-op (facts unchanged) |
| `REPORT_INTERPRETATION` | verified facts JSON → labeled interpretations + recommendations | facts-only report (interpretation section omitted) |

Invariants carried over: model proposes / code re-derives (D-026/D-038/D-046); structured
output → Pydantic → limited repair → deterministic fallback (§5.25.3); per-session and
per-pipeline-run cost ceilings; `MockBedrockProvider` keeps everything testable offline.
**Note:** real quality of every one of these is unverifiable until real Bedrock creds
exist (D-025 posture) — the mock proves plumbing and fail-closed paths only.

Streaming: **not** introduced in this plan. Chat replies return whole (structured call);
D-022/D-032 note token streaming needs a gateway `generate_stream` plus per-node SSE —
defer until chat latency proves painful (recorded as a tradeoff, §19).

---

## 7. Question-generation and validation pipeline (1.1)

Extends `packages/curriculum` (`ai_pipeline.py` grows a second entry point,
`generate_authored_candidate`; the shape pipeline stays for parameterized drill items —
the two modes complement each other).

Pipeline per candidate (offline CLI, `make question-gen` extending `pipeline_cli.py`):

1. **Generate** — `AUTHORED_QUESTION_GENERATION` with topic/skill/grade/difficulty rubric
   and few-shot exemplars; output includes stem, optional context block (scenario/table),
   4 options, answer, `answer_expression` when the answer is a computable value, canonical
   3-level hint ladder, worked solution, misconception tag per distractor,
   estimated time.
2. **Deterministic gate** (all code, any failure → `rejected` with reasons persisted):
   - Pydantic/schema (field presence, option count, markdown safety — no raw HTML/links).
   - **SymPy independent solve** when `answer_expression` parses: solve and compare to the
     declared correct option; also verify each distractor ≠ correct. (New dependency:
     `sympy` — boring, standard for this exact job, SPEC §5.8.5 names it.)
   - Exactly-one-correct among options (numeric/string normalization).
   - Answer-leakage: correct answer string not present in stem or hints below level 4;
     hint ladder monotonicity (level n must not contain level n+1's revealed content).
   - Hint/solution/answer agreement: solution's final answer == declared answer ==
     SymPy answer.
   - Wordlist + grade-band readability bound (deterministic heuristics; the LLM judge
     covers nuance).
   - **Near-duplicate:** embed the stem (`create_embedding`), cosine vs existing
     `stem_embedding`s over a threshold → reject; keeps the existing exact-match check.
3. **LLM review** — Solver A and Solver B (different models, §5.25.2) answer the item cold;
   disagreement with the deterministic answer rejects. Then `QUESTION_JUDGE` scores
   difficulty fit, ambiguity, curriculum alignment, age appropriateness/safety, and
   hint-quality; low scores reject, borderline sets `review_priority=high`.
4. **Persist** — template row (`authoring_mode="authored"`, `validation_status="pending"`),
   one static variant, one `question_validation_runs` row with every stage's result.
5. **Human review** — new `review_cli.py` (`make question-review`): lists pending sorted by
   `review_priority`, renders the item + pipeline evidence, approve/reject/edit-and-rerun.
   Approval calls the existing `activate_template` (D-026 unchanged: the pipeline can
   never self-approve).

Deterministic vs LLM vs human, explicitly: schema, solving, one-answer, agreement,
leakage, range, dedup, versioning = **code**; difficulty/ambiguity/alignment/safety
judgment and solver simulation = **LLM (different model from generator)**; final
activation, all `review_priority=high`, and all quarantine dispositions = **human**.
Runtime never generates: students only ever see `approved`+`active` rows (existing
`get_active_questions` filters already enforce this).

Versioning/audit: template `version` increments on edit-and-rerun with the prior row kept
(`validation_status="superseded"`); `question_validation_runs` is append-only; quarantine
flow (D-027) applies to authored items with zero changes.

## 8. Content-ingestion and refresh pipeline (2.3–2.5)

New workspace member `packages/webcontent` (mirrors `packages/knowledge`'s split, D-036):

1. **Fetch/extract CLI** (`make webcontent-sync`): `httpx` + `beautifulsoup4` (new deps,
   both boring) against the four official pages (branches, our-team, events, about).
   Per-page extractors emit:
   - Structured YAML records → `knowledge-content/structured/{branches,team,events}.yaml`
     (source_url, content_hash, extracted_at per record).
   - Markdown documents + manifest entries → `knowledge-content/documents/public/...`
     (audience `public`, real `effective_from` = today, replacing the placeholder
     branch-directory / academic-calendar / organization-overview docs via the same
     `document_id`s so `source_sha256` versioning applies).
2. **Human review is the gate:** the CLI writes files into the repo; a human reviews the
   git diff before running loaders — no auto-publish of scraped content (same posture as
   D-026's question gate). Extraction failures (site redesign) fail loudly and leave the
   previous files untouched (§6.17's "keep previous catalog" pattern).
3. **Loaders:** `make org-load` upserts `org_branches` / `org_team_members` / `org_events`
   by natural key + content_hash (D-016 idempotency); `make knowledge-load` (existing)
   ingests the documents into RAG. `mongo_fixtures.py` branch seeds are regenerated from
   `structured/branches.yaml` so the locator, profile adapter, and RAG all agree on one
   source of truth.
4. **Refresh:** re-run the CLI → diff → review → load. `last_verified_at` set on every
   touched row; unchanged hash = timestamp-only update; disappeared record → `status`
   flipped (`inactive`/`canceled`), never deleted. Scheduling stays manual in dev
   (EventBridge later, same as youtube-sync). Event status recomputation
   (upcoming→completed) is pure date logic at query time, not stored-state that can rot.
5. **Welcome/about (2.5):** `GET /chat/meta` serves a short welcome assembled from the
   ingested about document's summary chunk (provenance retained) + `chat_suggestions`
   rows; nothing hardcoded in prompts.

Also in scope here: **retire the 2026-08-01 date gate** — the refreshed manifests carry
real effective dates so retrieval works "today" (fixes 2.2 root cause #1).

## 9. Memory-consolidation design (1.7; supersedes/expands ROADMAP S17)

**Layer separation** (request's requirement, mapped to storage):

| Layer | Store | Retention |
|---|---|---|
| Raw interaction events | `learning_events` (structured, no free text beyond enum-ish payloads) | enrollment + policy (§5.15.2) |
| Raw chat | `tutor_chat_messages` | 90 days, purge job |
| Short-term session context | LangGraph checkpoint (`LearningState`) | 30/90 days per §5.15.2 |
| Episodic summaries | `MEMORY_CONSOLIDATION` intermediate (per-week summary rows in `learning_events` with `event_type="weekly_summary"`) | same as events |
| Stable semantic memory | `semantic_memory` | until `expires_at`/superseded |
| Mastery estimates | `mastery` (existing, stays separate — numeric model, not LLM memory) | current |

**Emission (trigger events):** answer submitted (correct/incorrect, response time),
intervention chosen + hint level, retry-ladder outcome label, chat turn (intent +
resolution only — *not* the message text; the text stays in `tutor_chat_messages`),
exam finalized, gain computed, video watched-link clicked.

**When consolidation runs:** (a) on `finalize_exam` post-exam completion — session-scoped
consolidation of that cycle; (b) weekly batch (`make memory-consolidate`, Sunday
EventBridge later) per §5.15.4. Idempotent per (student, week) — re-run = same facts
(ROADMAP S17's own done-when).

**Candidate production:** deterministic pre-aggregation first (counts, rates, streaks,
per-skill outcome labels — code, not LLM), then one `MEMORY_CONSOLIDATION` call with the
aggregates + chat-derived snippets (PII-minimized) + existing facts → `MemoryUpdate`
(facts_to_add/update/expire, each with `supporting_event_ids`, `confidence`, `fact_type`
from a closed enum: `strength / weak_skill / misconception / explanation_preference /
scaffolding_level / vocabulary_difficulty / guessing_pattern / hint_dependence /
improvement / effective_intervention / open_question / next_skill_recommendation`).

**Deterministic validation before upsert (fail closed):**
- Every `supporting_event_id` must exist, belong to the student, and fall in the window.
- Minimum-evidence rule: a *new* stable fact needs ≥3 supporting events across ≥2 sessions;
  below that it's stored as `status="provisional"` (never read by the tutor payload).
- `fact_type` outside the enum → dropped. Text mentioning names/emails (regex screen) →
  dropped. No personality/medical/psychological content: enum + a denylist screen.
- Contradiction: new fact conflicting with an active one (same fact_type+skill, opposite
  polarity) *demotes* rather than replaces — old fact `status="contested"`,
  `contradicts_event_count` incremented; only a second consecutive contradicting window
  supersedes (`superseded_by_id`). Prevents one bad day from re-labeling a student.
- Confidence decays: facts not reconfirmed within N weeks get `expires_at` set; expired
  facts are readable for audit, never served.

**Read paths (what memory affects):** `tutor.py`'s `relevant_learning_fact` (finally
populated — top fact by confidence for the current skill), `HINT_PERSONALIZATION` and
`TUTOR_CHAT` payloads, `study_plan.py` tie-breaking (prefer skills with `weak_skill`
facts), `video_catalog.search_video` (misconception tag in the query embedding), stage
narratives, and reports (1.8). Every read is by `student_external_id` with the same
server-side authorization as everything else; parents/tutors see facts only through the
report surface (which labels them as model-generated interpretations).

## 10. Frontend pages and component changes

### apps/learning-web (all new components in `src/screens/` + `src/components/` — new dir)

- `ExamScreen.tsx` → rebuilt around policy: `QuestionNavBar` (numbered chips:
  answered/unanswered/skipped/flagged/current; click-to-jump when policy allows),
  `ExamTimer` (remaining when timed, elapsed-per-question always; hidden if policy says),
  difficulty badge (growth-framed label, not "hard"), skip/flag buttons, keyboard nav
  (arrow keys + 1–4 option select + Enter submit, all buttons focusable, ARIA labels,
  `aria-live` for status changes), `SubmitConfirmationModal` (lists
  unanswered/flagged before finalize), autosave indicator ("saved" tick per selection —
  backed by the `PUT .../answer` upsert), streak/correctness feedback **removed for exam
  phases** (kept for study, where it's pedagogically fine).
- `AssistancePanel` replaces `InterventionScreen.tsx`'s chooser: four cards
  (Hint / Solution / Related Video / Chat); Hint card shows ladder position ("hint 2 of
  3"); Chat opens `TutorChatPanel` (message list, composer, inline hint/solution/video
  cards when the backend attaches one, "still stuck?" quick actions).
- `StageTransitionScreen` — full-width narrative card between phases (1.5), with an
  explicit "How we personalized this" evidence list (the same numbers the backend used).
- `StudentDashboardScreen` — new (1.8): mastery-by-skill bars, pre/post comparison,
  accuracy trend, time spent, hint usage, "what to do next" card; date-range picker
  (session/week/month/custom); "Generate my report" button → `ReportView` (one-page
  layout, three labeled sections: Verified results / What this suggests /
  Recommendations). Parent dashboard reuses the same components with the parent framing.
- Charts: **Recharts** (boring, dominant React chart lib) — first real frontend dep beyond
  React; hand-rolled SVG is the alternative if the dep is unwanted (decision in §19).
  (Implementation sessions must load the `dataviz` skill before writing chart code.)
- Refresh/disconnection recovery already works via sessionStorage + SSE snapshot; extend
  the snapshot consumption for `exam_overview` so a refresh mid-exam restores the nav bar
  state too.

### apps/chat-web

- `WelcomeCard` in `ChatScreen.tsx`: two-line welcome + 4–6 suggested prompt chips from
  `GET /chat/meta` (role-aware); shown until the first turn.
- `AccessHintBanner`: renders `access_hint` ("This is available to tutors — log in to
  see it") with a login shortcut to `DevLoginScreen`.
- Follow-up suggestion chips under each answer (`suggested_followups`).
- Optional `EventsCard` for calendar answers (structured list with upcoming/past styling)
  fed by the deterministic event payload.

## 11. Authentication and authorization behavior

Unchanged foundations: JWT audience split, server-side parent-child verification
(`authorization.py`), role/branch filters before retrieval (D-039), anonymous chat
(D-040), LLM never decides access (non-negotiable #3).

New behavior, all backend-enforced:

- **Access-aware refusal (2.1):** `RagRepository` gains
  `count_matching_by_audience(query_filters_without_audience)` returning
  `{audience: count}` only — called *only after* role-filtered retrieval returns empty;
  the mapping audience→"required login" message is a fixed dict in
  `role_access.py`. The chatbot's wording is generated from that dict, never from chunk
  content. A branch-restricted match for another branch is reported as generic
  ("branch-specific information — log in"), never naming the branch.
- **Learning chat and hints** run under the existing session authorization (student
  self / verified parent link); report endpoints check audience: student view for
  `Role.STUDENT` (self only), parent view via linked-children check, tutor/branch-manager
  views gated on those roles (first real use of §5.14.4 — keep the S13 caveat in mind:
  tutor/branch-manager have no branch resolution yet; their report scope should be
  explicit student-id-based and audited until real profiles exist).
- Dashboard/report DTOs never carry `skill_id`s outward (D-034 #4) and never carry PII —
  names are resolved per request from Mongo at the API boundary (D-020's pattern).

## 12. Reporting and visualization design (1.8)

- **Aggregation service** `services/dashboard.py`: pure Postgres reads over
  `assessment_attempts`, `study_attempts` (outcome labels), `learning_gain`, `mastery`,
  `hint_events`, `learning_events`; date-range filter pushed into SQL; returns typed
  DTOs. No LLM anywhere in the dashboard path — it must be cheap and always available.
- **Report generator** `services/report.py`: (1) collect verified facts (same aggregation
  service + memory facts labeled by status/confidence + intervention history); (2) one
  `REPORT_INTERPRETATION` call producing interpretation + recommendation sections; (3)
  deterministic validation that every number quoted in generated text appears in the
  facts payload (regex numeric extraction — numbers the model invents cause fallback to
  facts-only); (4) persist to `student_reports` with the three sections separated so the
  UI renders "Verified / Interpretation / Recommendations" with distinct visual
  treatment. Audience variants differ by which facts are included (student: growth
  framing, no confidence internals; parent: §5.14.3 style; tutor: unresolved skills +
  tutor_review flags + misconception facts; branch manager: cohort-level only — no
  per-student browsing beyond their remit).
- Visual encodings (implementation follows the `dataviz` skill): mastery = horizontal
  bars with target band; pre/post = paired bars per skill; gains over time = line;
  hint/solution usage = stacked proportion; difficulty progression = step line.

## 13. Evaluation strategy (extends ROADMAP S19)

- **Question pipeline evals:** a golden set of deliberately broken authored items (two
  correct options, leaked answer in hint 1, solution disagreeing with answer, off-grade
  vocabulary, near-duplicate pair) as fixtures — the deterministic gate must reject every
  one (pure pytest, runs in CI always). LLM-judge stages get a scripted-gateway harness
  (existing `_ScriptedGateway` pattern in `test_ai_pipeline.py`).
- **Hint/tutor evals:** leak detection executable evaluator (canonical answer string vs
  hint levels 1–3, per generated sample); LLM-as-judge rubric (age-appropriateness,
  addresses-the-misconception) runs only with real creds, skipped otherwise (D-008-style
  skip, ROADMAP S19's convention). Judge model ≠ tutor model (§5.31).
- **Memory evals:** synthetic event streams with known ground truth (e.g., 5 sign-error
  events → expect a `misconception` fact; 1 event → expect *no* stable fact); idempotency
  test (same week twice → identical facts); contradiction-demotion test.
- **RAG/chat coverage evals:** a golden Q&A set derived from the *real* ingested content
  (2.3/2.4) — ~40 questions with expected grounding document ids; measures
  answered-with-citation rate, refusal correctness (protected-content questions must
  produce `access_hint`, not answers), and no-hallucination (answers to
  out-of-content questions must refuse). This becomes the regression gate for retrieval
  config changes.
- **Exam-flow determinism:** identical inputs → identical grading/finalize results
  (extends §5.31.1 evaluator style already used in S10 tests).

## 14. Observability, logging, and tracing

Full observability is still ROADMAP S20; this plan adds only what its features need now:

- `question_validation_runs` and the existing `mcp_tool_calls` pattern give pipeline
  audit without new infra.
- Retrieval diagnostics (2.2): structured log record per retrieval (filter values, counts
  per stage: keyword/semantic/fused/reranked/final, no chunk text) behind a dev flag —
  the "why didn't it answer" tool. Formal trace spans wait for S20.
- Cost accounting: every new task flows through the gateway's existing per-call cost
  capture; new per-day per-student ceiling for `TUTOR_CHAT`/`HINT_PERSONALIZATION`
  (config in `learning_api/config.py`) since chat is the first *student-initiated
  unbounded* LLM surface (cost bug prevention).
- The S11 carry-over stands: `?token=` SSE query-string logging must be resolved at S20
  before real deployment.

## 15. Privacy and safety for K–12 (cross-cutting)

- **Free-text student chat is the big new exposure.** Messages from minors go to Bedrock
  (`TUTOR_CHAT`) and into `tutor_chat_messages`. Mitigations: deterministic PII screen
  before the wire and before storage (email/phone/URL regex redaction; name detection is
  unreliable — documented residual risk); 90-day purge job; transcripts never enter
  semantic memory or reports verbatim; scope guard keeps the tutor on-task (off-topic →
  fixed redirect, mirroring §5.19.4); self-harm/abuse-signal keyword screen routes to a
  fixed age-appropriate "talk to a trusted adult / your branch" message and flags for
  human review — never an LLM-improvised response. **This needs an explicit spec-level
  sign-off (§19), because §5.30.1's wire allowlist does not currently include free text.**
- Hints/solutions/narratives/reports: growth-oriented language enforced by prompt + the
  existing wordlist check extended to generated content; internal skill IDs never
  student-visible (D-034 #4); labels like difficulty shown with growth framing.
- Memory: closed fact-type enum, no personality/medical inference (§5.15.3 rule made
  executable), evidence-required, provisional-until-corroborated, contested-not-replaced
  (§9). Parents can see facts only via reports where they're labeled model-generated.
- Question bank: age-appropriateness is one of the LLM-judge dimensions *and* the
  deterministic wordlist; human activation is the final gate for all AI-authored content
  (D-026 kept).
- Web content: only the org's own public pages are ingested; team-member records are
  publicly published content but still get an explicit decision in §19 before being
  stored in Postgres (schema-purity test currently forbids person-name-shaped columns —
  `org_team_members.name` will need a deliberate, documented exemption or an
  external-id + Mongo pattern instead).

## 16. Testing strategy

Conventions kept: `make lint typecheck test` gates every session; `rollback_session` for
repository tests (D-013); nonsense marker phrases for content tests (D-018); skip-if-
unreachable for Docker deps (D-008); graph tests via `InMemorySaver` + `MockBedrockProvider`
(S13's `test_qa_graph.py` pattern); Playwright manual verification for frontend sessions
(D-034) with network-mocking where the date gate blocks real content.

Per-area, the load-bearing tests (details in each task, §18):

- 1.1: golden bad-item rejection suite; SymPy disagreement rejects; near-dup rejects;
  pending-not-approved lifecycle; review CLI activation round-trip.
- 1.2: save→finalize grading equals per-item grading on the same answers; finalize is
  idempotent (Idempotency-Key); skip/flag/jump state machine; 409 guard on paused tasks;
  policy matrix (hints blocked in pre/post, allowed in study).
- 1.3: ladder monotonicity; leak check per level; canonical fallback on gateway error;
  level persistence across refresh.
- 1.6: intent dispatch hits the real services (scripted gateway); exam-stage refusal;
  off-topic redirect; cost ceiling enforcement; PII redaction on the wire payload (extend
  `test_bedrock_payload_pii_floor.py`).
- 1.7: no fact without valid evidence ids; min-evidence provisional rule; idempotent
  week; contradiction demotion; expiry; purge job deletes aged chat rows.
- 2.x: access-probe never returns content fields; audience→message mapping; org_events
  date-logic (upcoming/completed/canceled); extractor golden-HTML fixtures (saved page
  snapshots so tests never hit the network); loader idempotency by content_hash;
  welcome/meta role-awareness.
- **Pre-existing debt to fix early** (it will bite these sessions hard):
  wrap `apps/learning-api/tests/*` HTTP tests in rollback/teardown (the S12 "Newly
  observed" unbounded-accumulation item) *before* adding many more HTTP tests, and fix
  the known-red S9 seed-collision test (PROGRESS documents the fix).

## 17. Migration and seed-data strategy

- One Alembic migration per session, `upgrade head`/`downgrade -1` round-tripped
  (existing bar). New NOT NULL columns on populated tables get `server_default` (D-028
  precedent).
- `question_templates.authoring_mode` backfills `"shape"`; existing rows untouched.
- Seed order for a fresh environment becomes: `make db-upgrade` → `curriculum-load` →
  `question-gen` (optional) → `org-load` → `knowledge-load` → `youtube-sync` →
  `seed-mongo`. Document in Makefile help.
- Replacing placeholder RAG docs: same `document_id`s + changed `source_sha256` →
  in-place chunk replacement (S12 design); the 3 deliberate draft fixtures stay for the
  draft-invisibility tests.
- `mongo_fixtures.py` branch data regenerated from `structured/branches.yaml` (one
  source of truth); existing fixture student/parent ids unchanged so every existing test
  keeps passing.
- Dev DB effective-date fix ships with the real-content ingestion (2.3) — no interim
  manifest hack.

## 18. Task breakdown and recommended order

Two largely independent tracks (chat track needs only S1–S3+S8-era foundations, same as
Milestone 3 did). Sessions sized to the existing half-day convention; each becomes a
ROADMAP entry. Recommended interleaving: **C1 → C2 first** (small, high user-visible
value, unblocks chat evals), then the learning track in order, then the remaining chat
polish anytime.

Dependency graph (summary):
L1 → L2 → L5 → L6 → L7/L9;  L3 → L4;  L8 independent after L1;  C1 → C2 → C3;
L6 (memory) also wants L5 (chat events) — matching PROGRESS's "S17 needs the graphs."

---

### C1 — Real org content: extraction pipeline + branches/team/about (2.3, 2.5-data, 2.2 root cause #1)
- **Objective:** replace placeholder branch/team/about content with reviewed content
  extracted from the four official pages; retire the future-dated manifest gate.
- **Files:** new `packages/webcontent/` (fetch, extractors, CLI, golden-HTML test
  fixtures); `knowledge-content/structured/*.yaml`; replaced
  `knowledge-content/documents/public/{branch-directory,organization-overview}` +
  manifests; new `packages/db` models/repos `org_branches`, `org_team_members`;
  `packages/adapters/src/intellichoice_adapters/seed/mongo_fixtures.py` regeneration.
- **Backend:** extractor per page type; `make webcontent-sync` + `make org-load`;
  branch data unification (locator `BranchInfo` ↔ `org_branches`).
- **Frontend:** none.
- **Data model:** two new tables + migration; manifests with real `effective_from`.
- **Tests:** extractor golden-fixture tests (no network); loader idempotency; RAG
  re-ingestion replaces placeholder chunks; locator still passes with real branch data.
- **Dependencies:** none.
- **Acceptance:** a live dev-server document_qa query about a real branch answers *today*
  with a citation to the ingested page; `org_branches` rows carry source_url +
  content_hash + last_verified_at; re-running sync with unchanged pages is a no-op.
- **Blocker to resolve first:** the `org_team_members.name` schema-purity question (§19).

### C2 — Structured events + calendar rewiring (2.4)
- **Objective:** real events with status/recurrence/timezone; calendar intent answers
  from the table, RAG extraction as fallback.
- **Files:** `packages/webcontent` events extractor; `packages/db` `org_events` (+repo);
  `apps/chat-api/src/chat_api/graph/nodes.py::calendar_extract`,
  `services/calendar.py`; `knowledge-content/documents/public/academic-calendar` replaced.
- **Backend:** deterministic event query (audience-filtered, date-classified);
  `GET /chat/events`; `.ics` path unchanged.
- **Frontend:** optional `EventsCard` in chat-web.
- **Data model:** `org_events` migration.
- **Tests:** date classification (upcoming/completed/canceled/recurring next-occurrence);
  fallback to RAG extraction when the table has no match; `.ics` from a structured event.
- **Dependencies:** C1 (pipeline + review conventions).
- **Acceptance:** "what events are coming up?" returns real dated events labeled
  current/upcoming; a past event is never described as upcoming; canceled events say so.

### C3 — Access-aware refusals, welcome, suggestions, coverage UX (2.1, 2.2, 2.5-UX)
- **Objective:** users understand what the bot can do and why something is protected.
- **Files:** `packages/db/repositories/rag.py` (audience-count probe);
  `chat_api/services/role_access.py` (audience→guidance map); `graph/nodes.py`
  (`explain_access` node + routing); new `GET /chat/meta`; `chat_suggestions` table+repo;
  `apps/chat-web` `WelcomeCard`/`AccessHintBanner`/follow-up chips.
- **Backend:** metadata-only probe after empty retrieval; welcome sourced from the
  ingested about doc; per-role suggestion sets; `suggested_followups` (deterministic:
  category-based, not LLM, initially).
- **Frontend:** welcome screen, suggestion chips, access banner, follow-ups.
- **Data model:** `chat_suggestions` migration + seed.
- **Tests:** probe never returns content; public query for tutor-only content yields the
  role-guidance message (graph test); logged-in tutor gets the real answer; welcome is
  role-aware; suggestions render.
- **Dependencies:** C1 (real content makes the happy paths real).
- **Acceptance:** anonymous "what's the tutor escalation procedure?" → "available to
  tutors — log in" with login shortcut; welcome card shows 2-line grounded intro + chips;
  golden Q&A coverage eval ≥ agreed threshold on the real content set.

### L1 — Authored question bank: schema + generation/validation pipeline (1.1)
- **Objective:** LLM-authored questions with canonical hints/solutions, validated and
  human-gated, deliverable through the existing exam/study paths.
- **Files:** `packages/db/models/questions.py` (+`question_validation_runs`),
  `repositories/questions.py`; `packages/curriculum/ai_pipeline.py`
  (`generate_authored_candidate`), `validation.py` (authored checks), new
  `review_cli.py`; `packages/shared/bedrock.py` (new tasks/payloads);
  `MockBedrockProvider` branches; `pipeline_cli.py`/Makefile.
- **Backend:** pipeline per §7; SymPy dep added; embedding dedup.
- **Frontend:** none (delivery shape unchanged — authored items render through the same
  `QuestionItem` DTO; `context_block` needs one additive optional field on it).
- **Data model:** template columns + runs table migration.
- **Tests:** §16's 1.1 list; existing shape-pipeline tests untouched and green.
- **Dependencies:** none (C-track independent). Real-credential runs deferred (D-025).
- **Acceptance:** `make question-gen` produces pending authored items with full audit
  rows; every golden bad item is rejected with recorded reasons; nothing reaches
  students without `make question-review` approval; a reviewed item appears in a real
  pre-exam via the unchanged selection query.

### L2 — Personalized hint ladder + canonical grounding (1.3)
- **Objective:** progressive, misconception-aware hints that cannot contradict the bank.
- **Files:** `learning_api/services/tutor.py`, `topic_resolver.py`; new `hint_events`
  model/repo; `graph/nodes.py::intervention_choice` (+`_generate_intervention_content`);
  `packages/shared/bedrock.py` (`HINT_PERSONALIZATION`, widened tutor payload — see §19
  decision); `AssistancePanel` ladder UI in learning-web.
- **Backend:** ladder state in `LearningState.assistance_level_by_variant`; canonical
  content source: authored items' stored ladder; shape items get deterministic canonical
  hints derived from their registry shape (one authored-by-hand ladder per shape — 10
  small dicts); leak/monotonicity checks on every personalized output; fallback = 
  canonical verbatim.
- **Frontend:** ladder position display; "next hint" affordance.
- **Data model:** `hint_events` migration.
- **Tests:** §16 1.3 list + PII-floor test update.
- **Dependencies:** L1 (canonical content shape); D-023 widening sign-off (§19).
- **Acceptance:** three successive hints escalate and never reveal the answer before
  level 4; a personalized hint referencing the student's actual wrong option addresses
  the mapped misconception (scripted-gateway test); gateway failure serves canonical.

### L3 — Assessment policy + exam backend (1.2 backend)
- **Objective:** save/skip/flag/finalize exam model with per-stage policy.
- **Files:** `services/flow.py`, `assessment_builder.py`, new `services/exam_policy.py`;
  `routers/sessions.py` (new exam routes); `graph/` (finalize node, state);
  `assessment_item_state` model/repo; migration.
- **Backend:** §4/§5 designs; correctness feedback stripped from exam-phase responses.
- **Frontend:** none yet.
- **Data model:** `assessment_item_state`, session policy columns.
- **Tests:** §16 1.2 list.
- **Dependencies:** none hard; before L4.
- **Acceptance:** full pre-exam via save→skip→return→finalize grades identically to the
  old sequential path on equal answers; refresh mid-exam restores statuses; finalize
  with unanswered items requires explicit confirmation flag in the request.

### L4 — Exam frontend: nav bar, timers, a11y (1.2 frontend)
- **Objective:** the student-facing exam experience.
- **Files:** `ExamScreen.tsx` rebuild + new `components/` (NavBar, Timer, Confirmation),
  `useLearningSession.ts`, `types.ts`.
- **Backend:** snapshot `exam_overview` field only.
- **Frontend:** §10 list (nav, timers, difficulty badge, keyboard, ARIA, autosave tick,
  confirmation modal).
- **Tests:** `tsc`+oxlint; Playwright click-through incl. keyboard-only run and
  refresh-restore of nav state (D-034 convention).
- **Dependencies:** L3.
- **Acceptance:** a keyboard-only user completes an exam; skipped question revisited via
  nav; no correctness signal visible during exams; per-question elapsed and remaining
  time render per policy.

### L5 — Contextual learning chat (1.6)
- **Objective:** on-question tutoring chat with deterministic intent shortcuts.
- **Files:** `graph/nodes.py::tutor_chat` + routing; `tutor_chat_messages` model/repo;
  `routers/sessions.py` chat routes; `services/tutor_chat.py`; shared `TUTOR_CHAT` task;
  PII screen util; learning-web `AssistancePanel`/`TutorChatPanel`.
- **Backend/Frontend/Data/Tests:** per §5, §10, §16 1.6.
- **Dependencies:** L2 (ladder is what "Hint" dispatches to); C-track scope-guard prior
  art (already merged); §19 free-text-to-Bedrock sign-off.
- **Acceptance:** "why is my answer wrong?" yields a misconception-grounded reply;
  "can I get a hint?" advances the real ladder and records `hint_events`; chat refuses
  during pre/post exam; per-day cost ceiling enforced and tested; transcript purge job
  removes >90-day rows.

### L6 — Memory consolidation (1.7; replaces ROADMAP S17)
- **Objective:** §9 in full — events, worker, validation, read paths.
- **Files:** `emit_events` helper into existing nodes; `packages/db` memory repo
  extensions; new `packages/memory` worker (or `learning_api/services/consolidation.py` +
  CLI — recommend a workspace package, D-009/D-014 precedent: it's offline logic shared
  with nothing FastAPI); Makefile `memory-consolidate`, `chat-purge`.
- **Backend/Data/Tests:** per §9/§16 1.7; migration for the two new columns.
- **Frontend:** none.
- **Dependencies:** L5 (chat events exist), L3 (finalize hook) — matches PROGRESS's note.
- **Acceptance:** ROADMAP S17's done-when (no fact without evidence; idempotent per
  week) + provisional/contradiction rules proven; `relevant_learning_fact` reaches the
  tutor payload for a student with an established fact.

### L7 — Stage narratives (1.5)
- **Objective:** grounded, personalized stage intros/outros.
- **Files:** `graph/nodes.py::stage_narrative`, `stage_transitions` model/repo, shared
  `STAGE_NARRATIVE` task, `StageTransitionScreen` in learning-web, snapshot field.
- **Tests:** evidence-injection check (every number in output exists in evidence);
  fallback template on gateway error; per-stage routing.
- **Dependencies:** L3 (finalize hook); better after L6 (memory enriches "tailored to
  you" claims with real facts) but can ship before with score-only evidence.
- **Acceptance:** post-pre-exam screen names actual weak topics (names, not ids) and the
  actual adaptation ("your study plan starts with X"); no narrative makes a claim absent
  from the evidence JSON.

### L8 — Khan Academy video bank hardening (1.4)
- **Objective:** official-channel-only real catalog with verification + richer matching.
- **Files:** `packages/adapters` new `youtube_data_api_provider.py` (real
  `YoutubeProvider`); `packages/youtube` (channel-ID pin, verification pass, transcript
  availability); `packages/db/models/youtube.py` columns; `video_catalog.py` (query
  enrichment: misconception + grade + mastery); migration.
- **Backend:** sync gains a verify step (`videos.list` status → inactive on
  gone/private); `suitability_status` gate added to `search_catalog` filters.
- **Frontend:** none (existing video card).
- **Tests:** channel-pin rejection of off-channel ids; verification flips status;
  enriched query still zero-external-calls at learning time.
- **Dependencies:** L1 optional (misconception tags), creds for the real provider
  (fake path testable regardless).
- **Acceptance:** only `channel_id == KHAN_ACADEMY_CHANNEL_ID` rows enter the catalog; a
  removed video stops being recommended after one sync; recommendation input includes
  grade band + misconception when available.

### L9 — Dashboard + student report (1.8)
- **Objective:** §12 in full.
- **Files:** `services/dashboard.py`, `services/report.py`, `student_reports` model/repo,
  `routers/students.py` routes, learning-web `StudentDashboardScreen`/`ReportView` +
  Recharts.
- **Tests:** aggregation correctness against seeded rows; date-range SQL; report numeric
  grounding check; audience gating; Playwright pass.
- **Dependencies:** L6 (memory + chat insights in reports; ship a facts-only report
  earlier if resequenced), L3 (accurate time data).
- **Acceptance:** dashboard renders all §12 visualizations with range filtering; report
  is one screen/page with the three labeled sections; parent and student views differ per
  §11; every quoted number traces to a stored fact.

### Cross-cutting session X1 (small, do early) — test-debt cleanup
Wrap `apps/learning-api/tests` HTTP tests in rollback/teardown; fix the S9 known-red
seed collision. **Do this before L3/L5 multiply the HTTP-test footprint.**

---

## 19. Major risks, tradeoffs, and unresolved decisions

**Needs an explicit decision before the affected session (spec-level):**

1. **Widening the §5.30.1 Bedrock allowlist** (D-023): hint personalization and chat need
   previous-hint summaries, misconception tag, attempt count, hint level — and chat needs
   the student's free-text message itself. Recommendation: amend SPEC §5.30.1 with an
   enumerated extension (all non-identifying) + a mandatory deterministic PII redaction
   pass on free text; update `test_bedrock_payload_pii_floor.py` accordingly. Without
   sign-off, L2 ships canonical-only ladders (still useful) and L5 is blocked.
2. **Team-member names in Postgres** (C1): `org_team_members.name` collides with the
   schema-purity denylist's intent. Options: (a) documented exemption for published-staff
   content (recommended — it is public web content, not user PII; keep the denylist test
   with an explicit allowlist entry); (b) keep team data only as RAG chunks, no
   structured table (loses structured answers). Decide at C1 start.
3. **Exam grading model change** (L3): save-then-finalize replaces grade-on-submit for
   pre/post. Alternative — keep immediate grading and just hide feedback — is cheaper but
   forbids answer changes and makes "review before submit" hollow. Recommendation: full
   change; it is the industry-standard assessment model and the flow.py surface is
   already isolated.
4. **Timed exams at all?** The timer *display* is built either way; whether pre/post get
   a `time_limit_seconds` default is an educational-policy call. Recommendation: untimed
   by default, policy field ready.

**Technical risks/tradeoffs:**

5. **Everything LLM-quality-dependent is unverifiable until real Bedrock creds exist**
   (D-025 posture): authored-question quality, judge reliability, hint quality, chat
   tone, narrative quality. The plan keeps every path testable with mocks and fail-closed,
   but expect a real-creds calibration session before any student sees generated content.
6. **Chat cost/abuse:** first student-initiated unbounded LLM surface. Mitigated by
   per-day ceilings + session budget + rate limiting, but the ceiling values are guesses
   until real usage.
7. **No token streaming:** chat replies arrive whole; multi-second latency possible.
   Deliberate deferral (gateway `generate_stream` + per-node SSE is its own session).
8. **Website extraction fragility:** a redesign breaks extractors. Mitigated by golden
   fixtures, loud failure, keep-previous-content; still a maintenance commitment.
9. **Memory overinterpretation** — the request's own warning. The provisional/
   min-evidence/contradiction-demotion rules are the defense; their thresholds (≥3 events,
   2 windows) are judgment calls to revisit with real data.
10. **Recharts dependency** vs hand-rolled SVG: recommend Recharts (boring, huge
    ecosystem); revisit only if bundle size matters.
11. **SymPy coverage limit:** word problems whose answers aren't clean expressions can't
    be machine-solved — those rely on solver-agreement + judges + human review; expect a
    higher human-review rate for scenario-heavy items (that is the correct posture, not a
    failure).
12. **`assessment_item_state` vs checkpoint duplication:** item status could live in
    `LearningState`, but the nav bar needs it queryable and the parent dashboard may too;
    a table with the checkpoint holding only ids follows the existing "domain tables are
    the record" S6 decision.
