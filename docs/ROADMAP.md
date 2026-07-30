# IntelliChoice Implementation Roadmap

This is the session-by-session plan for building the platform described in [SPEC.md](SPEC.md)
and, from S17 onward, the 2026-07-18 expansion plan
([plans/2026-07-18-expansion-plan.md](plans/2026-07-18-expansion-plan.md), "the plan" below).
Each session is scoped to fit comfortably in one Claude Code session (roughly a half-day of
focused work). Sessions within a milestone are ordered by dependency; milestones M4–M7 have
some flexibility (see Dependency notes).

**Renumbering note (2026-07-18, D-049):** sessions S17–S23 were restructured after S16 to
absorb the expansion plan. Old S17 (Memory) is now S25; old S18 (Multimodal) is S29; old
S19 (Evaluation) is S30; old S20 (Observability) is S31; old S21–S23 (launch track) are
S32–S34. PROGRESS.md/DECISIONS.md entries written before this date use the old numbers —
D-049 holds the full mapping.

**How to use this file:**
- Start each session with `/start-session S<n>` (reads this file + PROGRESS.md, confirms scope).
- End each session with `/end-session` (runs checks, updates PROGRESS.md).
- If a session runs long, cut scope, not quality — record the cut in PROGRESS.md as carry-over.

**Guiding principle (from SPEC.md §6.25):** accurate domain logic first — attendance,
authorization, grading, question quality, learning results. Agents, RAG, tools, and infra come
after the core is reliable.

**Dev-time substitutes:** local dev does not talk to the real `go.intellichoice.org` (a
MySQL-backed system — D-082/D-083; early sessions wrongly assumed MongoDB) or real AWS.
Every external dependency gets a local fake behind an interface (see DECISIONS.md D-002):
- Auth → local fake token issuer signing JWTs with the SPEC §5.1.2 claim set
- Org MySQL → Docker container (`mysql:8.4`) seeded with fixture users/attendance
- Bedrock → mock provider implementing the BedrockGateway interface (real calls optional via env)
- Gmail/Maps/Calendar MCP → console/fake transports that log instead of send

---

## Milestone 0 — Groundwork

### Session 0 — Planning setup ✅ (done 2026-07-13)
Roadmap, progress tracker, decision log, session skills, slim CLAUDE.md, git init.

### Session 1 — Repo scaffold and local dev environment
**Spec:** §5.2.1, §5.34.1 (structure only)
**Build:**
- Monorepo layout: `apps/learning-api`, `apps/chat-api`, `packages/shared` (Pydantic schemas), `packages/adapters`
- Python 3.12 + `uv`, `ruff`, `pyright`, `pytest` configured at the root
- `docker-compose.yml`: Postgres 16 + pgvector, MongoDB 7 (Mongo later replaced by MySQL 8.4 — D-082/D-083)
- Both FastAPI apps boot with `/healthz`; settings via pydantic-settings + `.env.example`
- `Makefile`: `up`, `down`, `test`, `lint`, `typecheck`, `dev-learning`, `dev-chat`
- GitHub Actions: lint + typecheck + test on PR
**Done when:** `make up && make test && make lint && make typecheck` all pass; both apps answer `/healthz`.

---

## Milestone 1 — Deterministic learning core (SPEC "Product Core")

### Session 2 — Auth validation and MongoDB Profile Adapter
**Spec:** §5.1.2, §5.4.1, §5.4.3, §5.4.4, §5.6.1, Phase 3 (§6.4)
**Build:**
- Fake token issuer (dev only) emitting JWTs with `sub, role, audience, parental_consent_verified, consent_version, student_age_band`, etc.
- Token-validation middleware: signature, expiry, audience (`learning` vs `chat`)
- Read-only Mongo adapter: student profile, parent→children, grade, branch, current-week attendance, branch-manager email
- Authorization dependency: parent-child relationship verified server-side, never trusted from the request
- Mongo seed fixtures: 2 parents, 4 students (1-child and 2-child cases), 2 branches, attendance present/absent/missing cases
**Done when:** Phase 3 completion criteria pass as pytest integration tests (student self-auth, parent limited to linked children, unknown attendance ≠ present).

### Session 3 — PostgreSQL domain schema and migrations
**Spec:** §5.4.2, §5.8.2, §5.15.2–5.15.3, §5.21.2, Phase 4 (§6.5)
**Build:**
- SQLAlchemy (async) models + Alembic migrations for: curriculum topics/skills, question templates/variants, assessment sessions/items, attempts, mastery, study sessions, learning gain, blocked sessions, problem reports, episodic events, semantic memory, RAG documents/chunks (pgvector column), evaluation results
- External-ID-only linkage to Mongo (`student_external_id` etc.) — no PII columns, enforced by a schema test that greps models for forbidden field names
- Repository layer skeletons with the predefined methods from §5.26.1
**Done when:** `alembic upgrade head` from empty DB is reproducible; every table has a repository with at least one round-trip test.

### Session 4 — Curriculum taxonomy and hand-authored seed questions
**Spec:** §5.7, §5.8.1–5.8.2, §5.8.5–5.8.6, first half of Phase 5 (§6.6)
**Build:**
- `curriculum/internal_math/` YAML: topics, skills, prerequisites, grade→topic mapping (start with 3 topics, e.g., linear equations, fraction operations, place value)
- Kumon reference folder with `source_manifest.yaml` (taxonomy reference only)
- Template model: `parameter_schema`, `solution_function`, distractor generators, constraints
- Deterministic variant generation from seeded RNG + executable validation (exactly one correct answer, unique options, no division by zero, values in range)
- ~10 hand-authored templates per difficulty for one topic (50 total) as the seed bank; loader script into Postgres
- Runtime random selection query (§5.8.6)
**Done when:** every loaded template passes the §5.8.5 validation suite; variant generation is reproducible from a seed.
**Note:** the LLM generation pipeline for scale is Session 9 — do not block on volume here.

### Session 5 — Deterministic learning vertical slice
**Spec:** §5.5.1 (flow), §5.6, §5.9, §5.10.1, §5.11.1–5.11.2, §5.13, §5.28.1, Phase 6 (§6.7)
**Build:**
- Endpoints from §5.28.1 (plain FastAPI services — LangGraph comes next session)
- Attendance gate: present → continue; absent/unknown → blocked with the §5.6.3 message; acknowledged-absence record
- Pre-exam: 10 fixed questions (2×5 difficulties), fixed set stored in `assessment_items`, Idempotency-Key on answer submission
- Deterministic grading, weighted bootstrap score (§5.10.1 weights), weak-skill extraction
- 5-question study plan via §5.11.2 priority rules (no interventions yet — wrong answers just advance)
- Post-exam parallel forms (same template family, new seed), learning-gain metrics incl. `not_applicable_pre_max`
**Done when:** an integration test drives one student through the entire flow via HTTP and asserts scores, gain, and idempotent resubmission.

### Session 6 — LangGraph workflow and PostgreSQL checkpointing
**Spec:** §5.5, §5.16, Phase 7 (§6.8)
**Build:**
- `LearningState` (§5.5.3) as a Pydantic model; graph nodes wrapping Session 5 services
- Conditional routing: role → child selection, attendance branches, phase transitions
- PostgresSaver checkpointing, `thread_id` = session, resume endpoint
- Error/timeout branches per §5.29
**Done when:** graph-route tests cover every branch in §5.5.1; killing the process mid-session and calling resume continues from the same question.

---

## Milestone 2 — Intelligence

### Session 7 — Human-in-the-loop interrupts
**Spec:** §5.1.4, §5.6.4–5.6.5, §5.11.3, Phase 8 (§6.9)
**Build:**
- `interrupt()` for: child selection (multi-child parents), attendance-email approval, hint/solution/video choice
- Interrupt surfaced through the API as `pending_interrupt` + a respond endpoint with Pydantic-validated payloads
- Attendance email draft (recipient/subject/body preview from §5.6.4) sent to a fake Gmail transport only after approval; session stays blocked
**Done when:** no external action fires without an approval record; pending interrupts survive restart (checkpointing test).

### Session 8 — Bedrock Gateway, Tutor Agent, structured outputs
**Spec:** §5.12, §5.25, §5.27, §5.30.1, Phase 9 (§6.10)
**Build:**
- `BedrockGateway` with: per-call timeout, bounded retry + backoff, max-token limits, per-session cost budget, circuit breaker, model registry by task (§5.25.2)
- Mock provider (default in dev/tests) + real Bedrock provider selected by env
- Structured output → Pydantic validation → limited repair retry → deterministic fallback (static verified hint)
- Tutor Agent, Hint/Solution generators (contexts from §5.11.4–5.11.5), Topic Resolver
- PII floor: only §5.30.1 fields ever cross the gateway — enforced by a request-model test
**Done when:** intervention flow returns validated hints/solutions; unit tests prove fallback on malformed model output; cost/token accounting is logged per call.

### Session 9 — LLM question-generation and review pipeline
**Spec:** §5.8.3–5.8.5, §5.8.7, second half of Phase 5 (§6.6)
**Build:**
- Offline pipeline (CLI/worker, not runtime): Generator → Solver A → Solver B → Difficulty/Ambiguity/Alignment reviewers → executable validation → dedup → activate/quarantine
- Problem-report endpoint + 5-distinct-user quarantine rule (§5.8.7)
- Run against mock provider in tests; real run generates candidates into `validation_status=pending`
**Done when:** nothing reaches `active` without passing every automated check; quarantine stops delivery without deleting history.

### Session 10 — Adaptive mastery and study planner
**Spec:** §5.10, §5.11.6–5.11.7, §5.13, Phase 10 (§6.11)
**Build:**
- Skill-level mastery updates, difficulty routing (±1), remediation questions beyond the base 5
- Retry policy ladder (§5.11.7) and outcome labels (`independent_correct` … `unresolved`); `correct_after_solution` excluded from independent mastery
- Video option wired to a stub catalog (real catalog in Session 14) with the §5.11.6 fallback message
- Tutor-review flags
**Done when:** identical inputs reproduce identical routing and scores (deterministic evaluator tests from §5.31.1).

### Session 11 — Learning frontend with SSE
**Spec:** §5.14, Phase 11 (§6.12)
**Build:**
- SSE endpoint streaming LangGraph events; browser client with auto-reconnect
- Student flow UI: child selection, attendance messages, exam screens, intervention chooser, progress/streak, growth-oriented result wording
- Parent dashboard (§5.14.3)
- Keep it plain: one small React (Vite) app; no state library until needed
**Done when:** refresh mid-session restores exact position; a full pre→study→post run works in the browser against local services.

---

## Milestone 3 — Q&A app, RAG, and tools

### Session 12 — RAG content foundation and ingestion
**Spec:** §5.20, §5.21.1–5.21.2, Phase 13 (§6.14)
**Build:**
- `knowledge-content/` repo structure with synthetic placeholder docs (every file carries the DRAFT banner) and manifests + JSON schemas
- LlamaIndex ingestion: structural chunking, metadata (audience, branch, academic_year, effective dates, status), embeddings → pgvector
- Local filesystem stands in for S3; the loader interface takes a bucket-style path so S3 is a config change later
**Done when:** ingestion is idempotent (re-run = no dupes via `source_sha256`); a status=draft doc is provably invisible to the retriever.

### Session 13 — Advanced RAG and the Q&A graph
**Spec:** §5.19, §5.21.3–5.21.8, Phase 14 (§6.15)
**Build:**
- Metadata filtering applied *before* retrieval; Postgres FTS + pgvector + Reciprocal Rank Fusion; reranker; citation-grounded `GroundedAnswer`
- QAState graph: auth detection, role resolution, Scope Guard (out-of-scope refusal §5.19.4), Intent Router, Response Verifier
- No-answer and conflicting-source policies; prompt-injection defenses (§5.30.4)
- `chat-api` endpoints from §5.28.2 (messages + stream)
**Done when:** role-filter tests prove a student query never retrieves tutor/manager chunks; unanswerable queries refuse with escalation offer instead of guessing.

### Session 14 — MCP tools I: Gmail, Calendar, .ics
**Spec:** §5.23, §5.24, Phase 15 (§6.16)
**Build:**
- MCP gateway/registry with Pydantic-validated tool arguments, timeouts, audit events
- Gmail tool (fake transport in dev): admin escalation + attendance email, both behind preview → `interrupt()` → approve
- CalendarEvent schema, Google Calendar tool (behind approval), RFC 5545 `.ics` generator with executable validation (§5.31.2)
- Anonymous-email protections: rate limit, body length cap, header-injection sanitization
**Done when:** tool-contract tests pass; invalid arguments never execute; every send has an approval + audit record.

### Session 15 — MCP tools II: Maps locator and YouTube catalog
**Spec:** §5.1.3, §5.18, §5.22, Phase 16 (§6.17)
**Build:**
- Location-consent flow; precise coordinates never persisted (assert nothing lands in DB/logs)
- Branch locator via Maps tool (fake provider in dev) with ZIP/city fallback and straight-line estimate fallback
- YouTube sync worker (manual trigger in dev; schedule later): catalog table from §5.18.2, embeddings, inactive marking
- `youtube_catalog.search` internal tool wired into the Session 10 video option
**Done when:** learning flow makes zero external YouTube calls; sync failure keeps the last valid catalog; consent tests pass.

### Session 16 — Chat frontend
**Spec:** §5.14.1 pattern applied to chat, §5.19
**Build:**
- Chat UI with streaming answers, citation display, approval modals (email/calendar/location), branch-locator UX, `.ics` download
**Done when:** an anonymous user can do FAQ + locator + `.ics` end-to-end locally; a logged-in parent sees role-gated answers.

---

## Milestone 4 — Real chat content and coverage (plan §18 C-track)

### Session 17 — Test-debt cleanup + real org content: branches, team, about ✅ (done 2026-07-19)
**Spec:** §5.20, §5.21.1–5.21.3; plan §8, §18-C1/X1 (request items 2.3, 2.5-data, 2.2 root cause #1)
**Decide at session start:** team-member names in Postgres vs the schema-purity denylist (plan §19 #2).
**Build:**
- Test-debt first (plan X1): wrap `apps/learning-api/tests/*` HTTP-committed tests in rollback/teardown (S12 "Newly observed" carry-over); fix the known-red S9 seed-collision test
- New `packages/webcontent`: fetch/extract CLI (`make webcontent-sync`) for the four official pages (branches, our-team, events, about) → structured YAML (`knowledge-content/structured/`) + Markdown docs/manifests replacing the placeholder public docs (same `document_id`s, real `effective_from`)
- New `org_branches`/`org_team_members` tables + repos + `make org-load` (natural-key + content_hash idempotency); `mongo_fixtures.py` (now `mysql_fixtures.py` — D-083) branch seeds regenerated from `structured/branches.yaml`
- Human review of the git diff is the publish gate; extraction failure leaves previous content untouched
**Done when:** a live document_qa query about a real branch answers *today* with a citation to the ingested page; re-running sync on unchanged pages is a no-op; extractor tests run against saved golden-HTML fixtures (no network); full suite green with no HTTP-test row accumulation across 3 repeated runs.
**Actual scope (see PROGRESS.md/DECISIONS.md D-050–D-053):** `intellichoice.org` turned out
to be a real org (D-051), not a fictional placeholder - the user supplied the real page
URLs. Events extraction stayed out of scope (S18, per this session's own title). Branch
locator/geolocation fixtures (`FakeMapsProvider`/`mongo_fixtures.py`'s — now `mysql_fixtures.py` — `BRANCH_MAIN`/
`BRANCH_NORTH`) were deliberately *not* unified with the real 26-branch `org_branches`
data (user-confirmed scope cut) - real branches power the RAG directory only this
session. `retrieval.py` gained a real rerank-score filter (D-052), found necessary once
real content was genuinely retrievable for the first time. All four "Done when" criteria
verified live and via 3 repeated `make test` runs (270/270 stable).

### Session 18 — Structured events and calendar rewiring ✅ (done 2026-07-19)
**Spec:** §5.23; plan §18-C2 (request item 2.4)
**Build:**
- Events extractor in `packages/webcontent`; new `org_events` table (start/end, timezone, audience, branch, registration, RRULE, status) + repo + loader; placeholder `academic-calendar` doc replaced
- `calendar_extract` queries `org_events` first (deterministic upcoming/completed/canceled/recurrence date logic); existing RAG-extraction path kept as fallback; `calendar_action`/`.ics` unchanged
- Optional `GET /chat/events` + `EventsCard` in chat-web
**Done when:** "what events are coming up?" returns real events correctly labeled current/upcoming; a past event is never described as upcoming; a canceled event says so; `.ics` generation works from a structured event row.
**Actual scope (see PROGRESS.md/DECISIONS.md D-054/D-055):** events come from the org's
Tribe Events Calendar REST API, not HTML scraping (found live, richer/more reliable) -
all 42 real events are historical, so upcoming/canceled/recurring classification is
unit-tested against synthetic dates rather than demoed live; a new `calendar_event_
listing` node answers generic listing queries without an interrupt; `GET /chat/events`
was built, the `EventsCard` chat-web component was not (deferred, ROADMAP marked it
optional). All four "Done when" criteria verified (live where real data allows, tested
otherwise); 292/292 tests passing across 3 repeated runs.

### Session 19 — Access-aware refusals, welcome message, and suggestions
**Spec:** §5.19.1–5.19.4, §5.21.3; plan §18-C3 (request items 2.1, 2.2, 2.5-UX)
**Build:**
- Metadata-only audience probe in `RagRepository` (counts + audiences only, content never leaves the repository layer), called only after role-filtered retrieval is empty; fixed audience→"requires X login" map in `role_access.py`; new `explain_access` graph node; `access_hint` on the message response
- New `GET /chat/meta`: 2-line welcome grounded in the ingested about document + role-aware suggested prompts (`chat_suggestions` table + seed)
- Deterministic follow-up suggestions per answer; chat-web `WelcomeCard`, `AccessHintBanner`, suggestion chips
- Golden Q&A coverage eval set (~40 questions) derived from the real ingested content, as versioned fixtures
**Done when:** an anonymous tutor-procedure question yields the role-guidance message (never content) while a tutor token gets the real answer; the probe provably returns no content fields; welcome + suggestions render per role; the coverage eval passes its agreed threshold.

---

## Milestone 5 — Question bank and assessment experience (plan §18 L1–L4)

### Session 20 — Authored question bank: generation and validation pipeline ✅ (done 2026-07-19)
**Spec:** §5.8.2–5.8.5; plan §7, §18-L1 (request item 1.1)
**Build:**
- `question_templates` gains `authoring_mode` ("shape"|"authored") + authored-content columns (stem/context block/answer_expression/canonical 3-level hint ladder/canonical solution/stem_embedding/review_priority); new `question_validation_runs` audit table; authored items get one static variant so delivery paths (§5.8.6 selection, grading, quarantine) are untouched
- `generate_authored_candidate` pipeline: LLM generation → deterministic gate (schema, SymPy independent solve where parseable, exactly-one-correct, leakage + ladder monotonicity, hint/solution/answer agreement, wordlist/readability, embedding near-dup) → Solver A/B (different models) → `QUESTION_JUDGE` reviews → `pending`
- New `review_cli.py` (`make question-review`): human activation via the existing `activate_template` — the pipeline can never self-approve (D-026 unchanged)
- New deps: `sympy`; new Bedrock tasks with `MockBedrockProvider` branches
**Done when:** every golden bad-item fixture (two correct options, leaked answer, disagreeing solution, off-grade wording, near-duplicate) is rejected with persisted reasons; nothing reaches students without human review; an approved authored item appears in a real pre-exam via the unchanged selection query.

### Session 21 — Personalized hint ladder grounded in the bank ✅ (done 2026-07-19)
**Spec:** §5.11.4–5.11.5, §5.30.1; plan §18-L2 (request item 1.3)
**Decide at session start:** widening the §5.30.1 Bedrock allowlist (D-023; plan §19 #1) — without sign-off this session ships canonical-only ladders.
**Build:**
- Progressive disclosure: `assistance_level_by_variant` in `LearningState`, new `hint_events` table; hand-authored canonical ladders for the 10 existing shapes; authored items use their stored ladders
- `HINT_PERSONALIZATION` task: rewrite of the canonical hint using wrong option/misconception tag/attempt count/hint level/`relevant_learning_fact`; deterministic leak + monotonicity checks on every output; fallback = canonical verbatim
- Learning-web `AssistancePanel` with ladder position ("hint 2 of 3")
**Done when:** three successive hints escalate and never reveal the answer before the final level; a personalized hint addresses the mapped misconception (scripted-gateway test); gateway failure serves the canonical hint; the PII-floor test covers the widened payload.
**Actual scope (see PROGRESS.md/DECISIONS.md D-062/D-063):** allowlist widening was
user-approved for `HINT_PERSONALIZATION` only (a new, separate, narrowest-necessary
payload — `TUTOR`'s own payload is untouched). The registry actually holds **11** shapes,
not 10 (`two_step_sub_b`/`both_sides_alt`; the roadmap text was stale) — all 11 got
hand-authored ladders. The within-question loop is a graph-level self-loop (conditional
edge back to `intervention_choice`), not an intra-node interrupt loop — chosen after
verifying a `while`-loop would replay and re-run every earlier round's real Bedrock call
on each escalation (D-021 gotcha #1); this is the first multi-round-pause node in the
codebase and sets the pattern (D-063). Misconception-tag mapping is a coarse ordinal-rank
heuristic (student's wrong option → same-index `common_error_tags` entry), not a true
per-distractor-generator trace — flagged as future work in PROGRESS.md if hint quality
demands it. All four "Done when" criteria verified live (scripted Playwright run against
the real dev server) and via 3 repeated `make test` runs (358/358 stable).

### Session 22 — Assessment policy and exam backend ✅ (done 2026-07-20)
**Spec:** §5.9, §5.13; plan §18-L3 (request item 1.2 backend)
**Decide at session start:** save-then-finalize grading model + whether pre/post exams are timed (plan §19 #3–4; recommendation: full model change, untimed by default with the policy field ready).
**Build:**
- Per-session-type `AssessmentPolicy` (timing, navigation, review, hint availability, feedback visibility); policy snapshot + `time_limit_seconds`/`finalized_at`/`topic_id` on `assessment_sessions`; new `assessment_item_state` table (saved option, unseen/answered/skipped/flagged, per-item time)
- Exam routes: `PUT .../exam/items/{id}/answer` (save, not grade — plain repository write, not a graph turn), `/skip`, `/flag`, `GET .../exam/overview`, `POST .../exam/finalize` (grades everything into `assessment_attempts`, idempotent, graph `finalize_exam` node)
- Correctness feedback stripped from exam-phase responses (the streak counter currently leaks it); study phase (D-028 ladder) untouched
**Done when:** save→skip→return→finalize grades identically to the old sequential path on equal answers; finalize is idempotent and requires explicit confirmation when items are unanswered; hints are refused in pre/post and allowed in study (policy matrix test); refresh mid-exam restores item statuses.
**Actual scope (see PROGRESS.md/DECISIONS.md D-064):** user-decided at session start
*against* both plan recommendations — grading stayed **grade-on-submit** (each `/answers`
call grades immediately, as every prior session did), not save-then-finalize, and pre/post
exams got a **real default timer** (1200s), not untimed-by-default. Consequence: an
*answered* item can never be revisited/changed, only unanswered items support skip/flag/
jump — S23 must not build a resubmit affordance for answered items. The plan's
`PUT .../exam/items/{id}/answer` "save, not grade" route was **not built** — its reason to
exist doesn't apply once grading stays on the existing `POST .../answers` path (now
masking `is_correct` for exam phases instead). Phase auto-advance was removed for pre/post
exams (an explicit `POST .../exam/finalize` — a real "Submit exam" — is now required even
when every item is answered, since skip/flag/jump means "last item answered" no longer
implies "done"); study phase is untouched. All four "Done when" criteria hold under this
adapted model (tested + live-verified against the real dev server — see PROGRESS.md).
**Found and fixed one real cross-session issue via this session's own verification:**
`question_variants` has no cleanup path in the test suite's per-student sweep (D-053) and
had silently accumulated enough duplicate content over the project's history to collide
with `test_ai_pipeline.py`'s deliberately-chosen S17 anti-collision seed — see D-064's own
entry for the fix and the still-open follow-up.

### Session 22.5 — Brand identity and design tokens ✅ (done 2026-07-19)
**Spec:** none (off-spec visual work); plan: [plans/2026-07-19-branding-plan.md](plans/2026-07-19-branding-plan.md)
— that file carries the full brand audit (colors/fonts/logo extracted from the live
`www.intellichoice.org` theme CSS), token mapping, codebase recon, and per-phase task
list; read it instead of re-deriving any of that. Frontend-only: no backend/DB/
LangGraph/RAG/eval changes.
**Build:**
- `packages/ui-brand/` shared token source (tokens.css keeping the existing semantic
  token names, base.css, logo assets, favicon, `check_contrast.py`), wired into both
  apps (`@fontsource` Poppins 600 / Open Sans 400+700 self-hosted per the plan's BD2,
  `server.fs.allow` in both vite configs, `main.tsx` imports)
- App chrome: learning-web shell header+footer via the `view()` wrap described in the
  plan's recon; chat-web logo inside the existing `.chat-header` (do **not** add a
  shell bar there — see the plan's `calc(100svh - 48px)` caveat); DevLogin logo;
  favicons
- Component/screen pass per the plan: uppercase 600 action buttons with the
  `.option`/`.card`/`.link`/`.chip` content-class exclusions; pink→purple gradient as
  a sparse highlight device; WCAG-darkened interactive tones (plan BD3);
  dark-scheme brand variants (plan BD4)
- Log the plan's BD1–BD5 decisions into DECISIONS.md (next free D-numbers)
**Done when:** both apps `npm run build` + `npm run lint` clean; a Playwright screenshot
walk of every screen in light + dark shows the brand applied with no layout breakage;
`check_contrast.py` passes ≥4.5:1 for every text/background token pair in both schemes;
student-facing wording unchanged (SPEC rule 10).
**Ordering note:** runs before S23 on purpose — the exam UI should be built on brand
tokens once, and S23's accessibility criteria can reuse the contrast tooling introduced
here.

### Session 23 — Exam frontend: navigation, timers, accessibility ✅ (done 2026-07-20)
**Spec:** §5.14.2; plan §10, §18-L4 (request item 1.2 frontend)
**Build:**
- `ExamScreen` rebuild: `QuestionNavBar` (answered/unanswered/skipped/flagged/current, click-to-jump per policy), `ExamTimer` (remaining when timed, per-question elapsed), difficulty badge (growth-framed), skip/flag, autosave tick, `SubmitConfirmationModal`
- Keyboard navigation (arrows, 1–4 option select, Enter) + ARIA labels + `aria-live` status; correctness/streak UI removed for exam phases, kept for study
- `exam_overview` on the SSE snapshot so refresh restores the nav bar
**Done when:** a keyboard-only Playwright run completes a full exam including skip-and-return; no correctness signal is visible during exams; refresh mid-exam restores nav state; `tsc`/oxlint clean.
**Note from S22 (D-064):** grading is immediate, not deferred to finalize — clicking an
*answered* item in the nav bar must show it read-only (no correctness, matching the
existing masked `is_correct`), never let the student change/resubmit it. Only unseen/
skipped/flagged items are real jump targets. `GET /learning/sessions/{id}/exam/overview`
(item statuses + `remaining_seconds`) already exists and is what S22's own tests use to
verify refresh-restore — reuse it rather than re-deriving statuses client-side.
**Actual scope (see PROGRESS.md/DECISIONS.md D-070/D-071):** `exam_overview` is fetched by
`ExamScreen` directly (mount + after every mutation + a 20s poll), **not** embedded in the
SSE snapshot as this bullet originally suggested — user-decided at session start (D-070) to
avoid an `AssessmentRepository` round-trip on every action response for every phase, since
the endpoint the ROADMAP text itself already treats as the refresh-restore source of truth
covers it. New `POST .../exam/items/{id}/time` route + `AssessmentRepository.
add_item_time` back the autosave tick (`assessment_item_state.time_spent_ms`, unpopulated
since S22). **Found and fixed a real cross-cutting bug via this session's own Playwright
verification, not previously known:** a mid-exam refresh restored nav-bar *statuses*
correctly but lost the question *content* entirely (stuck on "Loading the next
question…") — `graph/nodes.py`'s `submit_answer`/`finalize_exam` nodes were writing
`"last_items": None` explicitly on every exam-phase answer, clearing the checkpointed
batch LangGraph's default merge would otherwise have preserved. Fixed by omitting the key
instead (D-071); also affects/fixes the same class of gap for a mid-hint-ladder refresh in
`study`. All four "Done when" criteria hold (live-verified via a keyboard-only Playwright
walk: full exam completion incl. skip-then-return-via-nav-bar, an answered item rendering
read-only, no correctness signal in the DOM at any point, and a full-content nav-bar
restore after a real page reload) — see PROGRESS.md for the full verification transcript.

---

## Milestone 6 — Tutoring chat, memory, personalization (plan §18 L5–L9)

### Session 24 — Contextual learning chat ✅ (done 2026-07-20)
**Spec:** §5.12, §5.30; plan §5, §15, §18-L5 (request item 1.6)
**Decide at session start:** free student text to Bedrock + deterministic PII redaction (same D-023-class sign-off as S21; plan §19 #1) — hard blocker for this session. **User-approved** the full option (redaction + payload extension), not the plan's "deterministic-only chat" fallback.
**Build:**
- `tutor_chat` graph node: scope guard with learning intents (question_help/request_hint/request_solution/request_video/why_wrong/off_topic); the four assistance intents dispatch deterministically to the existing hint ladder, solution, and video services; free replies via a new `TUTOR_CHAT` task; per-stage gate (refused during pre/post exam)
- `tutor_chat_messages` table (90-day retention + purge job); PII redaction screen before wire and storage; self-harm/abuse keyword screen → fixed age-appropriate response + human-review flag; per-day per-student cost ceiling
- Chat routes + learning-web `TutorChatPanel` behind the 4-option `AssistancePanel` (Hint / Solution / Related Video / Chat)
**Done when:** "can I get a hint?" advances the real ladder and records `hint_events`; "why is my answer wrong?" yields a misconception-grounded reply; chat refuses during exams; the cost ceiling and the PII redaction are both proven by tests; the purge job removes >90-day rows.
**Actual scope (see DECISIONS.md D-073):** chat is **not** a graph node/`entry_action` as
planned — empirically, both a fresh `graph.ainvoke` and `graph.aupdate_state` silently
discard a pending `intervention_choice` interrupt (confirmed via a scripted check: `/respond`
409'd "no interrupt is pending" immediately after one `aupdate_state` call), and that pause
is exactly when the button-panel `AssistancePanel` — and now chat, alongside it — is shown.
Fixed by making `graph/nodes.py::run_chat_turn` a plain service call (same "not a graph
turn" precedent as S22/S23's skip/flag/time-tracking routes), invoked directly from
`routers/sessions.py`, never through the graph. Two narrow, documented consequences (D-073):
chat's own hint-ladder-level tracking reads the durable `hint_events` table instead of
`LearningState.assistance_level_by_variant` (can drift from the button panel's own tracking
only if a student mixes both channels for the same wrong attempt in the same pause); chat's
Bedrock spend isn't persisted back into the checkpoint's per-session budget total (the
per-day cost ceiling, backed by the real `tutor_chat_messages` table, is chat's actual cost
control and doesn't share this gap). All five "Done when" criteria hold — 9 new backend
tests plus a live Playwright run that chatted three times (hint/why_wrong/off_topic) during
an open `intervention_choice` pause and then confirmed the original "Show the solution"
button still worked afterward, proving the pause survived.

### Session 25 — Memory system *(old S17, expanded per plan §9)* ✅ (done 2026-07-20)
**Spec:** §5.15, Phase 17 (§6.18); plan §9, §18-L6 (request item 1.7)
**Build:**
- Episodic `learning_events` emission from existing nodes (answers, interventions + hint level, ladder outcomes, chat turns as intent-only, exam finalize, gain) — the backfill emit points anticipated in M1/M2
- Consolidation worker (new workspace package; `make memory-consolidate`, EventBridge later): deterministic pre-aggregation → `MEMORY_CONSOLIDATION` call → `MemoryUpdate` → deterministic validation (evidence ids must exist/belong/fit window; closed fact-type enum; name/email screen; no personality/medical facts) → upsert
- Anti-overinterpretation rules: new facts `provisional` until ≥3 events across ≥2 sessions; contradiction demotes (`contested`) rather than replaces; confidence decay + `expires_at`; retention jobs per §5.15.2
- Read paths: `tutor.py`'s `relevant_learning_fact`, hint/chat payloads, study-plan tie-breaking, video search, (later) narratives and reports
**Done when:** no semantic fact exists without valid `evidence_event_ids`; consolidation is idempotent per (student, week); a single contradicting event demotes but does not delete; a student with an established fact gets it in the tutor payload.

### Session 26 — Personalized stage introductions and transitions ✅ (done 2026-07-20)
**Spec:** §5.10.3, §5.13.3 (evidence sources); plan §18-L7 (request item 1.5)
**Build:**
- `stage_narrative` graph node after pre-exam finalize, study completion, and post-exam finalize (static variant at stage entry); evidence assembled deterministically (scores, weak-skill *names*, gain, planner's actual next step, memory facts where available)
- New `STAGE_NARRATIVE` task + `stage_transitions` table; deterministic template fallback; numeric-grounding check (every number in output must exist in the evidence JSON)
- `StageTransitionScreen` with an explicit "How we personalized this" evidence list; `stage_narrative` on the SSE snapshot
**Done when:** the post-pre-exam screen names the student's actual weak topics and the actual adaptation; no narrative contains a number absent from its evidence; gateway failure renders the template fallback.
**Actual scope (see DECISIONS.md D-075):** all 5 stages from the plan's schema table
shipped (`pre_intro`/`pre_outro`/`study_step`/`study_outro`/`post_outro`), not just the
3 this entry's own build list names - user-approved at session start, with newly-invented
trigger definitions for the 2 ROADMAP never specified (`pre_intro`: first real SSE
connect; `study_step`: a genuine skill transition, never a same-skill retry). Not a real
graph node/new edges - an inline helper called from `finalize_exam`/`submit_answer`/
`intervention_choice` (same "not every side effect needs a node" precedent as D-073),
plus the SSE connect path for `pre_intro` specifically (outside any graph turn). All 3
literal "Done when" criteria hold. Also found and fixed a real, pre-existing,
cross-cutting bug via this session's own live verification: `useLearningSession.ts`'s
SSE connect raced ahead of session checkpoint creation and silently never recovered
(`EventSource` doesn't retry a non-2xx response) - see D-075 #4.

### Session 27 — Khan Academy video bank hardening ✅ (done 2026-07-20)
**Spec:** §5.18; plan §18-L8 (request item 1.4)
**Build:**
- Real `YoutubeProvider` (YouTube Data API v3) behind the existing Protocol (fake stays the dev default, D-002); catalog pinned to the official Khan Academy channel ID — off-channel ids rejected at sync
- New columns: prerequisite skills, transcript availability/language, license, `last_verified_at`, `suitability_status`, verification failures; sync gains a verification pass (`videos.list` status → inactive on gone/private, reversible)
- `search_video` query enrichment: misconception tag, grade band, mastery state; `suitability_status` added to catalog filters; still zero external calls at learning time
**Done when:** only official-channel rows enter the catalog; a removed video stops being recommended after one sync; recommendation input includes grade band + misconception when available; sync failure keeps the previous catalog (existing S15 property preserved).

### Session 28 — Progress dashboard and student report ✅ (done 2026-07-20)
**Spec:** §5.14.2–5.14.4; plan §12, §18-L9 (request item 1.8)
**Build:**
- `services/dashboard.py`: pure-Postgres aggregates (mastery by skill, pre/post comparison, accuracy trends, time, attempts, hint/solution usage, difficulty progression) with date-range filtering pushed into SQL — no LLM in the dashboard path
- `services/report.py`: verified facts → `REPORT_INTERPRETATION` → numeric-grounding validation (invented numbers ⇒ facts-only fallback) → `student_reports` row with Verified/Interpretation/Recommendations separated; audience variants (student/parent/tutor/branch-manager) gated server-side
- Learning-web `StudentDashboardScreen` + `ReportView` (~one page); charts via Recharts (load the `dataviz` skill before writing chart code); parent dashboard reuses the components
**Done when:** all listed visualizations render with range filtering; every number in a generated report traces to a stored fact; student and parent views differ per the authorization rules; a keyboard/Playwright pass is clean.

---

## Milestone 7 — Multimodal, quality, ops

### Session 29 — Multimodal solution images *(old S18, unchanged)* — **deferred, not built (D-078)**
**Spec:** §5.17, Phase 18 (§6.19)
**Build (not started):**
- Upload endpoint: type/size validation, ephemeral encrypted storage, VLM analysis (mock in dev), Pydantic + executable math validation of extracted steps, immediate deletion on success *and* failure, deletion metric
- Image-analysis consent interrupt; VLM output feeds hints only, never the score
**Done when:** a test proves the file is gone after both success and failure paths; no image bytes or filenames in logs/traces.
**Deferred 2026-07-20 (user-declined at session start, see D-078):** photo uploads from K-12 minors raise a privacy/consent question the spec's existing §5.1.4/§5.17.2 language doesn't fully resolve (a "solution photo" can incidentally capture a face, other homework, or a home background), and every supporting piece (real malware scanning, real S3 encryption-at-rest) is still on the D-002 "no real creds yet" footing — this session would only stack fakes on fakes without resolving the actual open question. Revisit this entry (design reference stays as-is) once the privacy question, not just the architecture, has an answer.

### Session 30 — Evaluation platform *(old S19 + plan §13 extensions)* ✅ (done 2026-07-20)
**Spec:** §5.31, Phase 19 (§6.20); plan §13
**Build:**
- Golden datasets (learning + Q&A cases from §5.31.4) as versioned fixtures — including the S19/S20-era sets already created (coverage Q&A, bad-item fixtures), promoted into one harness
- Deterministic and executable evaluators as pytest suites; LLM-as-judge harness (different model than production answerer) — runs only when creds present, otherwise skipped
- Expansion evals per plan §13: hint leak detection, memory ground-truth/idempotency/contradiction cases, report numeric grounding, exam-flow determinism
- CI gate: regression thresholds block merge
**Done when:** a deliberately broken grading rule fails CI; judge harness runs against staging creds; the plan-§13 suites are wired into the same gate.
**Shipped 2026-07-20 (see D-080 for the full design):** new `packages/evals` (registry
mapping every SPEC §5.31.1-§5.31.4 item to its existing test coverage, rather than
rewriting the already-passing S19/S20 fixtures into a generic data-driven engine; real
`BedrockTask.LLM_JUDGE` wiring with a judge model distinct from the production answerer;
a hint-leak-detection golden fixture that found and fixed a real bug, D-079: negative-
integer answers were never caught by the old `\b`-anchored leak check). Exam-flow
determinism landed as a pure-function evaluator in `apps/learning-api/tests/` (not
`packages/evals`, to keep packages from depending on an app). Not built: a dedicated
prompt-injection fixture (deferred to S33); "SQL parser validation" (no NL2SQL feature
exists to validate, CLAUDE.md non-negotiable #2); the image-deletion-event evaluator
(S29 deferred, D-078).

### Session 31 — Observability *(old S20, unchanged scope + carried caveats)* ✅ (done 2026-07-21)
**Spec:** §5.32, Phase 20 (§6.21)
**Build:**
- Structured JSON logging with the §5.32.3 PII denylist enforced by a log-schema test
- OpenTelemetry spans across FastAPI → LangGraph → gateway → DBs → tools under one trace_id
- LangSmith wiring with masking config; Prometheus `/metrics` with the §5.32.4 KPIs; Grafana dashboards as code
- Resolve the standing D-032 caveat (`?token=` SSE values in access logs) before real deployment
**Done when:** one request's full path is visible under a single trace_id locally (otel-collector + Jaeger in compose).
**Shipped 2026-07-21 (see D-081 for the full design):** new `packages/observability`
(JSON logging + PII denylist, OTel tracing, Prometheus KPIs, JSON access log, env-gated
LangSmith); both apps wired at startup; `docker-compose.yml` gained `otel-collector`/
`jaeger`/`prometheus`/`grafana` + provisioned config under `observability/`. D-032
resolved (route-template-only access logging, uvicorn's raw access logger disabled).
Found and fixed two real instrumentation-ordering bugs via live verification against a
running Jaeger (`FastAPIInstrumentor`/`PymongoInstrumentor` both silently dropped spans
when instrumented from inside `lifespan` instead of at module level) — the literal "Done
when" criterion was verified live, not assumed: one real HTTP flow produced a single
trace_id spanning FastAPI → LangGraph → Postgres, and a separate call produced FastAPI →
Mongo. Alerting is rules-only (no Alertmanager/real notification channel — no creds
exist); CPU/memory/pod-count metrics deferred to S32 (no deployed container runtime yet).

---

## Milestone 8 — Launch track (decision-gated)

### Session 32 — Deployment architecture decision + first deploy *(old S21)* ✅ (done 2026-07-22)
The spec prescribes AWS Organizations + EKS + Terraform + Aurora (§5.33–5.34). For a solo
maintainer at ~1,000 MAU, my recommendation (see DECISIONS.md D-004, corrected 2026-07-22 —
see D-082/D-083) is to **defer EKS** and launch on a simpler footprint — ECS Fargate or a
managed container platform + RDS Postgres w/ pgvector — keeping the spec's environment
separation and security posture. (D-004's original text also said "+ managed Mongo"; drop
that — `go.intellichoice.org`'s real database is MySQL, not MongoDB, *and* it's pre-existing
external infrastructure IntelliChoice doesn't own or provision, so there is no managed
database for this project's own deployment to stand up on its behalf — only network
reachability and read credentials to the existing system.) The apps are containerized either
way, so EKS remains a later migration, not a rewrite. Decide this at session start, then:
Terraform for whichever footprint, staging env, secrets, domains/TLS, CI deploy to staging.
**Shipped 2026-07-22 (see D-084 for the full design and every real bug found/fixed live):**
confirmed ECS Fargate + RDS PostgreSQL/pgvector + RDS MySQL. A real `intellichoice-staging`
AWS environment is live - VPC/ALB/ECS cluster, both services healthy, both RDS instances
migrated+seeded, both frontends on S3+CloudFront (same-origin path routing, no domain/TLS
needed yet), real Bedrock wired in and proven working end-to-end. CI deploy to staging is not
wired yet - blocked on the user completing `gh auth login`/GitHub repo creation; Terraform's
GitHub OIDC role is ready but not created. Domains/TLS deferred (no domain registered).

### Session 33 — Security hardening *(old S22; Phase 21, §6.22)*
WAF/rate limiting/CAPTCHA, RBAC audit, secret rotation, dependency + container scanning,
prompt-injection test suite, data/image-deletion verification, backup-restore test.

### Session 34 — Load testing and production readiness *(old S23; Phase 22, §6.23)* ✅ (done 2026-07-24)
k6 scenarios for the §6.23 targets, failure drills (DB failover, Bedrock throttling, MCP outage),
canary pipeline (Phase 23), rollback triggers. **Shipped 2026-07-24 (see D-095 for the full
design and every real finding):** all four built, several deliberately translated from SPEC's
EKS/HPA/SQS-shaped literal wording to this project's real ECS Fargate architecture (see D-095) -
k6 scenarios + drills run locally against docker-compose (no live AWS access this session
either); canary pipeline is a bake-then-check gate in `deploy-staging.yml`, not a true
traffic-split canary (`desired_count=1` has no second task to shift traffic to); rollback
triggers are both an ECS deployment circuit breaker (deploy-time) and CloudWatch-alarm-gated
automatic rollback (runtime). Two real production bugs found and fixed by the load test itself
(rate-limiter self-DoS + invisible 429s, `/healthz` never checking DB connectivity). All Terraform
was `fmt`/`validate`-clean at session end. **AWS access returned mid-session after this write-up**
(see D-095's "Addendum 2026-07-24") - two RDS instances and two IAM fixes were applied for real,
and this project's first-ever real `deploy-staging.yml` run surfaced (and mostly fixed) several
more real bugs, but the live deploy itself is still failing and carries over open - see
PROGRESS.md's "Next session" for the concrete resume point. Real load testing against live
staging is a separate, still-open carry-over once the deploy itself is unblocked.

## Milestone 9 — Audit, stabilize, then integrate with the production system

**[docs/INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) is the detailed source for this milestone**
(scope constraint, boundary tiers, the incompatibility catalog I1–I15, the auth-option
comparison, accepted residual risks). The blocks below are the session-by-session view only —
read the plan's own sections rather than duplicating its reasoning here.

The governing constraint: **the production system behind intellichoice.org /
go.intellichoice.org (`icrest`/`icweb` + the `ic` MySQL database) is immutable.** All
compatibility logic lives in the new stack. Phase 0 exists because this project's own history
shows that live verification finds real defects unit tests miss — S23, S26, S28, S31, S33, S34
and S35 each did — so "497 tests pass" is not evidence of readiness for integration.

### Session 35 — Restore the deploy pipeline *(INTEGRATION_PLAN §2.2)* ✅ (done 2026-07-24)
Diagnose the failing Alembic step (real traceback never seen), apply the withheld Terraform
(canary bake + CloudWatch alarms + autoscaling + deployment circuit breaker + per-app JWT
signing secrets), verify both service deploy steps, confirm a real image healthy under
`/readyz`. **Shipped 2026-07-24 (see D-096):** the real error was
`InvalidPasswordError` - D-092's `manage_master_user_password` had rotated the master password
into RDS's managed secret while `ops-task` still injected the dead one, so **S34's decision to
withhold the apply until a deploy succeeded was the blocker, not a safeguard**. Withheld Terraform
applied; migrations pass; both services healthy on revision 12 under `/readyz` (which proves real
Postgres + MySQL connectivity). **A P0 was found live: `POST /dev/token` had been reachable on both
public CloudFront distributions for two days** because S33's fix existed only in gitignored
`terraform.tfvars` with the apply withheld - now closed and guarded by a live post-deploy assertion.
Also fixed: the pipeline could never be re-run on an unchanged commit (SHA tag + immutable ECR
tags), and `*.tfplan` was not gitignored despite embedding a cleartext copy of state.
Finished on this project's **first fully green deploy** (run `30121887429`, every step, CI green on
the same push), with the canary bake, frontend sync, and smoke test all exercised live for the first
time and the results independently re-verified afterwards.
**Open:** the SNS alarm email subscription is confirmed and active, but §2.6 criterion 8 needs an
*induced* alarm proving delivery end-to-end (S39's operations audit). **Note for S36:**
closing `/dev/token` leaves staging with no authentication path at all until S44, which blocks the
audits' live end-to-end runs as specified - decide at S36's start (D-096's closing section).

### Sessions 36–39 — Phase 0A audit *(INTEGRATION_PLAN §2.3)*
Common method for all four: requirements traceability against launch-scope SPEC sections;
defect-pattern sweeps for every bug class this project has already produced once; adversarial
end-to-end runs against live staging (not happy paths); findings logged with severity
(§2.4 P0–P3), reproduction, and evidence. Fixes land in Phase 0B, not mid-audit, except P0s,
which stop the line.

- **S36 — AUD-L, learning product correctness.** Assessment creation/policy snapshots,
  generation+validation pipelines, attempt/answer flows incl. finalize idempotency,
  deterministic scoring and re-grade consistency, mastery + retry ladder vs §5.10–5.11, the
  full hint ladder, learning-gain math, dashboard/report numbers recomputed independently from
  raw rows, stage-narrative grounding, memory effects on tutoring payloads.
- **S37 — AUD-C, chat product correctness.** ⏸ partial (2026-07-25, D-101) Retrieval quality via the
  existing eval harness extended (paraphrase/adversarial/no-answer sets; grounded-citation and
  correct-refusal rates as tracked metrics), pre-retrieval role/branch/date filtering for every
  audience incl. anonymous, conversation state across turns/interrupts/reconnects, tool-call
  validation + audit trail, citation verbatim checks, **every degraded/refusal/empty response shape
  actually rendered** (the S22.5 blank-turn bug is the known exemplar of a class).
  **Shipped:** 16 findings (AUD-C-01..16), three P1 — a thread-ownership hole verified live, a scope
  prompt that refuses "What is IntelliChoice?", and precise coordinates persisting in
  `checkpoint_writes`. The eval was measured against **both** the mock and real Bedrock, which is what
  showed that the suite's 100% scores were measuring `MockBedrockProvider` rather than retrieval.
  **Why ⏸ and not ✅ — two sub-items of this line are not met as written.** (1) "every
  degraded/refusal/empty response shape **actually rendered**": all 14 shapes were enumerated against
  `ChatScreen`/`App` and two were found broken (AUD-C-04, AUD-C-10), but by reading the render code,
  not by rendering a page — no browser automation exists in this environment. (2) "reconnects" was
  exercised programmatically (`_initial_snapshot` plus the event bus, which is how the anonymous
  eavesdrop in AUD-C-01 was demonstrated), not by dropping and resuming a real SSE connection.
  **This is the same gap S36 left**, and it now blocks the same thing twice: the browser-driven half
  of §2.3 is uncovered for both the learning and the chat app. Fold it into S39 (AUD-F), which already
  owns scripted journeys with console/network capture, or run it wherever browser tooling first
  becomes available.
- **S38 — AUD-X, cross-cutting integrity.** ⏸ partial (2026-07-25, D-102) New-stack authn/authz
  boundaries (audience separation, cross-student/parent attempts on every route, SSE `?token=`,
  dev-token gates, checkpoint-thread hijack), checkpoint↔domain-table consistency after crashes
  mid-node/mid-interrupt/mid-finalize, idempotency of every retryable write, Bedrock cost ceilings
  under concurrency, PII floor re-verified against **live staging** logs/traces/metrics/payloads.
  **Shipped:** 8 findings (AUD-X-01..08) plus AUD-C-16 settled and upgraded **P3 → P1** — staging's
  corpus is 159/159 mock hash vectors, so its semantic channel has never worked. Five P1: a
  session-hijack write reproduced on live staging (AUD-X-01), SPEC §5.1.2's `parental_consent_
  verified` check absent entirely (AUD-X-02), a tutor token finalizing another student's exam
  (AUD-X-05), checkpoint↔domain divergence leaving sessions in an unrecoverable 500 loop
  (AUD-X-07), and every per-day cost ceiling racing under concurrency at **8× the ceiling**
  (AUD-X-08). AUD-X-06 fixed in-session because it left the test baseline intermittently red.
  **Why ⏸ and not ✅ — one sub-item cannot be evidenced:** `OTEL_ENABLED` is **false** on both
  staging services, so the "**traces**" half of the PII-floor line is unevidenced rather than
  passing (logs, stored payloads and metrics are all clean, each with a positive control). Enabling
  it is a deploy-time config change, folded into S39 along with the same criterion-9 requirement.
- **S39 — AUD-F, frontend contracts + operations.** ⏸ partial (2026-07-25, D-103) Scripted walk of every launch user journey
  against the real APIs with console/network capture, CI-coverage inventory (chat-web has no CI
  job at all), deployment drills (a deliberate bad-image deploy must demonstrably auto-roll-
  back), scheduled-job dry runs, proof each CloudWatch alarm can fire *and reach a human*,
  live-staging load/perf re-run.
  **Carries three items from earlier sessions:** the **browser-driven half of §2.3** for *both*
  apps (S36 and S37 each left it — no browser automation exists in this environment yet), the
  **induced-alarm delivery proof** S35 left open, and **enabling `OTEL_ENABLED` on the two staging
  services then re-running the PII scan against traces** — the one S38 sub-item that could not be
  evidenced, and a §2.6 criterion-9 requirement in its own right.
  **Shipped:** browser automation now exists (Playwright in `e2e/`, `make e2e`), and **the
  browser-driven half of §2.3 is closed for both apps** — all 18 chat response shapes render, and
  AUD-C-04/10/11 are reproduced visually, confirming S37's code-reading conclusion. 9 findings
  (AUD-F-01..09), one P1: `App.tsx`'s inline-arrow callbacks sit in `ExamScreen` effect dependency
  arrays, so **885 `POST .../time` fire during a 15-second dwell on one question and 76
  `GET exam/overview` per 10-item exam at a median 30 ms gap against a declared 20 s poll**. It
  also corrects AUD-L-14's evidence. AUD-F-09 fixed in-session — a defect in this session's own
  change that would have crash-looped every later deploy.
  **Why ⏸ — the four remaining items all mutate staging** and this session had no standing
  authorization for them: the `terraform apply` of the ADOT sidecar (written, plan clean), the
  induced-alarm proof, the bad-image rollback drill, and the live load run. Baseline recorded for
  the trace work: **X-Ray held 0 traces over 6 hours**.
  **Two findings change Phase 0B's shape.** **AUD-F-06:** no EventBridge rule or schedule exists at
  all, so criterion 6's ≥1-week unattended clock has not started — **the earliest gate pass is one
  week after the schedules land**, which makes them an early-S40 item; and only **three** of the
  four jobs are schedulable, since `webcontent-sync` rewrites tracked content and wants a human
  diff review. **AUD-F-02:** criterion 3's "zero console errors" is unmeetable until the
  post-finalize 409 burst (35 in 96 ms) is fixed.

### Sessions 40–41 (elastic) — Phase 0B stabilization *(INTEGRATION_PLAN §2.5)*
All P1s + cheap P2s from the audits, merged with the seeded known-issues backlog: S22.5
`access_hint` blank turn, S11 parent auto-select, chat-web CI, the unseeded-RNG flake,
`question_variants` accumulation, the ~249k-row `checkpoints` sweep, ~~EventBridge schedules for
the four manual jobs~~, retention jobs for `stage_transitions`/`student_reports`, and the ≥2-task/
autoscaling P95 fix with a live load re-baseline.
**✅ EventBridge schedules landed 2026-07-26 (D-105), first item of S40** — deliberately first,
because criterion 6's ≥1-week unattended clock is the only gate item bounded by the calendar. It
started **2026-07-26**, so the earliest possible gate pass is **2026-08-02**. Re-scoped from four
jobs to **two enabled** (`chat-purge` daily, `memory-consolidate` weekly): `webcontent-sync` expects
a human diff review, and `youtube-sync` is DISABLED because it would refresh the catalog from a
*fake* provider every week. Building it found **AUD-F-15 (P1)** — `chat-purge` had never once run
against the deployed database, so the 90-day retention promise had never been kept.
**Two S38 P1s need a specific verification shape, not just a fix (D-102):** AUD-X-08's ceiling
race must be re-verified **with a concurrent arm** — the sequential test passes today and would
keep passing after a bad fix — and AUD-X-07's cheap remedy is replacing the `assert`s on
checkpointed row ids with a reconciliation path, *not* reordering the two commits.
**AUD-F-14 adds a third of that kind:** the ≥2-task/autoscaling fix must change the scaling
*signal*, not just the task count — the current CPU target-tracking policy cannot fire on an
I/O-bound workload (CPU peaked at 15% while p95 sat at 31s), so raising `max_capacity` alone would
change nothing.

**✅ The authorization cluster landed 2026-07-27 (D-107), four P1s in one pass:** AUD-X-01 (session
seizure), AUD-X-05 (tutor *writes* — the read half stays with D-086/S43), AUD-X-02 (SPEC §5.1.2's
consent claims, previously read by nothing) and AUD-C-01 + AUD-C-04 together, as D-101 requires.
Taken first because they share one root shape and one test surface, **and because S44 replaces auth
outright — the regression tests want to exist before that happens.** All four re-verified live on
staging with before/after pairs. **Also ✅ the `question_variants` accumulation item (D-106)**, fixed
by scoping SPEC §5.8.3's dedup population rather than by another row delete; it was the fourth
recurrence and had turned the baseline red at session start. **`question_variants`/`checkpoints`
orphan sweeps are now optional hygiene, not prerequisites** — they no longer gate anything.
**✅ The criterion-3 cluster landed 2026-07-27 (D-109):** AUD-F-01's per-render request storm
(**899 → 1** time reports and **903 → 2** overview fetches in a 15-second dwell, re-verified by
counting requests as D-103 §2 required), AUD-F-02's console-error burst (**35 → 0**, and it turned
out *not* to share AUD-F-01's root cause — the AUD-F-01 fix left exactly 1), and the e2e
intermittency, which was **three unrelated harness races** rather than the single shared-state
story S39 recorded. Suite now **green three consecutive whole-suite runs**. Both probes promoted
from `test.fail()` to regression tests, each watched failing with its own fix reverted.
**✅ The integrity/concurrency cluster landed 2026-07-27 (D-110):** AUD-L-10 (one attempt per exam
item, enforced by a unique constraint rather than a check, since a check is the same read-then-act
shape) and AUD-X-08 (a `cost_reservations` ledger with an advisory lock, reserve-then-settle,
**10/10 generated at 10.0× the ceiling → 1/10 at 1.0×**), plus **half of AUD-X-07** — seam (a),
mid-finalize, now rolls the checkpoint back to what the database supports instead of dead-ending.
**The verification shape D-102 required was the load-bearing part twice over:** each fix has a
concurrent arm that fails without it while every sequential test still passes, and AUD-X-08's
reproduction had to be *repaired before it could reproduce* — with the mock provider's ~0 ms call
the unfixed ceiling measured 1/10, i.e. clean.
**Seven P1s remain** (AUD-L-04, L-07 read half, C-02, C-03, C-16, X-07 half, F-14).
**AUD-X-07 stays open:** seam (b) (mid-interrupt) needs a paused LangGraph node *completed*, not
channel values edited, and fix shape (1) — one transaction across both stores — is untouched.
**One new P2, AUD-F-16:** `reuseExistingServer: true` had the audit measuring two-day-old API
code, so every S39/S40 `local` e2e result is of an unknown application version.

### Gate — measurable exit criteria before integration discovery *(INTEGRATION_PLAN §2.6)*
Nine criteria, evidenced in PROGRESS.md: full traceability; zero open P0/P1; every launch
journey passing twice consecutively against live staging; 3 consecutive green full test runs
with CI covering every deployable; 2 consecutive clean deploys incl. migrations + canary bake
plus one demonstrated auto-rollback; scheduled jobs running unattended ≥1 week; live load
meeting the S34-calibrated thresholds with ≥2 tasks; every alarm induced once and reaching a
monitored inbox; zero PII in live staging logs/traces/metrics/payloads.

**Standing as of 2026-07-29 (post-D-114).** **5 met** (six consecutive clean pipeline deploys plus the
demonstrated auto-rollback; the "consecutive" ambiguity D-105 left open is settled — `73396c1` →
`c58d1fe` has no failed deployment between them on either reading). **6 is on the calendar,
read per-job (D-114 §3)**: earliest 2026-08-02 for the original two schedules, **2026-08-05**
for the `retention-purge` schedule (applied and ENABLED 2026-07-29). **4 is met**
(D-111: `chat-web` and `e2e-typecheck` CI jobs landed; AUD-F-08 closed).
**2 needs two more P1 halves**: AUD-L-07 (read half — but see the ordering note below) and
AUD-X-07 (half), both with written dispositions. **D-115 added and closed two more P1s in one
session** (AUD-X-09 the dead reranker, AUD-X-12 the false-refusal token cap) plus two P2s
(AUD-X-10 circuit blast radius, AUD-X-11 success-only logging) — so criterion 2's count is
unchanged, but note that **both new P1s existed and were invisible during every previous
assessment of this criterion**; "zero open P1s" measures what has been found. The chat cluster closed AUD-C-16, AUD-C-02
and AUD-F-19 (D-112), AUD-F-20 closed with D-111's deploy-time re-seed, D-113 closed AUD-C-03
(merged and deployed 2026-07-29, PR #38; staging probe pending) and AUD-F-14 (latency step
scaling, live-verified 1 → 3 under load), and D-114 closed AUD-L-04 (retention purges for
`semantic_memory`/`stage_transitions`/`student_reports`, schedule apply pending).
**7's "≥2 tasks under load" is demonstrated, and D-115 diagnosed and removed what made its
threshold leg unmeetable.** The ~26 s gap was a rerank call that had never once succeeded
against real Bedrock (AUD-X-09); with it fixed, a live 74-turn run at concurrency 5 across
3 tasks measures **p50 9.57 s / p95 15.94 s, 0 errors, 0 circuit-open refusals** (was p50 28.8 /
p95 32.8, with 9 of 114 turns refused in 30 ms). **The threshold itself now needs a decision, and
"redo the S34 calibration" turned out to be the wrong framing** (D-115 §11): `chat_qa.js`'s
`p(95)<1000` is *correct for what it measures* — a mock-provider server answering deliberately
non-matching "zqxv" queries, i.e. app overhead with no model in the path — and should stay.
What criterion 7 lacks is a **separate live-staging threshold for a real grounded turn**, which
cannot be under ~8 s because such a turn is four sequential model calls. Measured component
budget behind the 15.94 s:

| component | p50 | p95 |
|---|---|---|
| `scope_and_intent` | 1.89 s | 2.53 s |
| `create_embedding` | 0.10 s | 0.14 s |
| `hybrid_search` (3 SQL) | 0.04 s | — |
| `rerank` | 2.92 s | 3.76 s |
| `rag_answer` | 4.16 s | **10.62 s** |
| end-to-end turn | 9.57 s | 15.94 s |

**✅ Decided 2026-07-29 (D-116 §1): p95 ≤ 20 s and error rate < 1% at concurrency 5 with ≥2
tasks** — 25% headroom over a measurement stable at p95 ≈ 16 s across three runs (15.94 / 16.29 /
16.09). This is a live-staging threshold **explicitly distinct** from `chat_qa.js`'s mock-backed
`p(95)<1000`, which is correct for what it measures and stays. Its instrument is
`load-tests/k6/chat_qa_staging.js` (`make load-staging-chat`): guest turns through the real
CloudFront edge, a custom `chat_turn_duration` trend so the cheap session-create call cannot
flatter the p95, and sub-1 s 200s counted as failures so a run cannot pass by refusing quickly.

**✅ Executed 2026-07-29, and criterion 7's chat leg passes on its first real run.**
70/70 turns, **140/140 checks**, all three thresholds green:

| metric | result | threshold |
|---|---|---|
| `chat_turn_duration` p95 | **16.68 s** (med 9.89, max 19.64) | < 20 s ✅ |
| `http_req_failed` | **0.00%** (0 of 140) | < 1% ✅ |
| `chat_fast_refusals` | **0** | == 0 ✅ |
| tasks | **3 running** | ≥ 2 ✅ |

The custom trend earned its place: `http_req_duration` reports med **3.51 s** against the turn's
real med of **9.89 s**, because the near-instant session-create call is half the requests. A
threshold read off the default metric would have been measuring the wrong thing.
**Still unmeasured: criterion 7's learning-app leg** under authenticated load.

**✅ The same 20 s closed AUD-X-13, applied and live-verified.** `terraform apply`: 0 add,
2 change, 0 destroy. The before/after is unusually clean because the alarm's own history supplied
a "before" the finding never had — it flapped **ALARM↔OK three times in 100 minutes** on real
traffic that morning (10:57/11:05, 11:51/12:05, 12:25/12:36). After the change, the load run above
produced four consecutive minutes of ALB p95 at **14.59 / 15.16 / 16.58 / 17.84 s** — every one
over the old 3 s threshold, and three is all it needs — and **the alarm never left OK**.
learning-api stays at 3 s; the scale-out alarm stays at 3 s deliberately.
**The dominant term is answer length, not infrastructure**: `rag_answer` p50 emits 501 output
tokens (~375 words) and its p95 10.62 s is time spent generating prose. So the lever that would
move this number is asking for a shorter answer — which SPEC §5.10.3's age-appropriateness
argues for independently — not more tasks or a faster model. Carried as an item, not done here:
a prompt change is product-visible and needs its own before/after measurement.
**Criterion 7's learning-app leg is still unmeasured** under authenticated load (the staging
token secrets are retrievable, D-107 §10). **3 is close but not claimable:
the last two staging e2e runs are 47 passed / 2 failed / 4 skipped, twice, against two different
deploys** — every chat journey passes with a working semantic channel underneath (D-112), and the
weekly-expiry caveat is gone (the deploy re-seeds). The two failures are both learning-side
staging-only observations with no IDs yet (PROGRESS: the time-telemetry dwell that looks like
AUD-F-01's signature despite the fix being deployed — check the served-bundle identity,
AUD-F-16's ask — and the post-finalize narrative stall, the AUD-F-04/05 displacement family under
staging latency). Diagnose those two and criterion 3 is two clean runs away. The two conditional
`test.skip()`s (no suggestion chips; no dashboard entry point) should also stop being conditional
before the criterion is claimed.
**✅ The stale-bundle hypothesis is dead, measured 2026-07-29 (D-116 §3).** It was the leading
explanation for the time-telemetry failure and it is wrong. Two independent identities:
- **API** — ECS runs `gha-12508257ac10` on both services (task definitions 33 and 32), i.e. PR
  #43's merge, far newer than AUD-F-01's S41 fix.
- **Served SPA bundle** — this is the one that actually matters, because AUD-F-01's fix is in
  `App.tsx`, not the API. Rebuilding `apps/learning-web` locally at HEAD with the deploy's own
  `VITE_LEARNING_API_URL=""` emits `index-be8gjEfS.js`, the **same content-hashed filename**
  CloudFront serves, and the served file is **byte-identical** (SHA-256
  `63eca681…7dd1055`).

So staging is serving exactly what `main` builds, AUD-F-01's fix included.

**✅ Diagnosed the same day: both failures are one defect, AUD-F-21 (P1, filed not fixed).**
The staging suite reproduced **47 passed / 2 failed / 4 skipped** for a third consecutive run.
AUD-F-01's fix demonstrably *works* on staging — 1 time report (was 899), 0 overview fetches
(was 903); what fails is the dwell's **value** (2116 ms against a 15,000 ms dwell).
`App.tsx:199` renders `StageTransitionScreen` as a **sibling** of `ExamScreen`, not above it, so a
stage narrative arriving 2.1 s into the dwell *unmounts* the exam screen and flushes a truncated
measurement; the same branch explains the post-finalize stall, since `StageTransitionScreen` has
no `.phase-chip` for the journey's 60-second wait to find. Staging-only because the narrative is an
LLM call — ~26 ms on the mock, seconds on real Bedrock.
**Criterion 3 is now blocked on exactly one change**, which is a better position than two
undiagnosed observations. The fix is product-visible (should a late narrative interpose at all?)
and needs its own decision, so it was filed rather than absorbed here.
**✅ That change is made, 2026-07-29 (D-117 §1): the narrative renders above the phase screen, and
is dropped once the student has interacted in the current phase.** Verified locally, including a
new spec that delays the SSE connect so the ~26 ms mock reproduces real Bedrock's timing — the
first time this defect class is visible outside a staging run. Local e2e 56 passed / 1 skipped.
**Both `test.skip()`s named above are also gone, and neither was tidiness:** the chips test had
been counting the DOM before `/chat/meta` resolved and skipping itself on every run since S39
(**AUD-F-23**, P3, fixed — that journey has now been driven once), and the parent-dashboard skip's
message was itself the defect (**AUD-F-22**, P2, filed — the dashboard button exists only on
`StartScreen`, gated on a `studentId` a parent gets by starting a session, and on `ResultsScreen`).
**⛔ Criterion 3 still cannot be claimed, and the reason changed twice before it was understood.**
AUD-F-21's fix deployed and the failure did not close; AUD-F-24's fix deployed and it *still* did not
close. The dwell read 2116 → 1578 → 1653 ms across three staging runs. The actual cause is
**AUD-F-26** (P1, fixed, D-119): `_initial_snapshot` responded with state read *before* a ~2.3 s
Bedrock call, so a client that started its pre-exam inside that window was pushed back to topic
selection — which is what flushed a truncated dwell and what stalled `journey-student`. Both earlier
fixes were real defects and stand; neither was what the tests measured. **The answer was in
`journeys.jsonl`'s millisecond timeline from the first staging run.**
**AUD-F-25 (P2) fixed and verified live** — `/chat/meta` returns 4 suggested prompts (was `[]`); the
ops-task image had a dangling editable install of `chat_api`, so the seeder could not run there at
all, and `deploy-staging.yml` now runs it.
**All of it is merged and deployed (`26a56f6e`, run 30510841185 success). What is owed is the
measurement: two clean `make e2e-staging` runs**, which the expiring AWS session cut off before the
first one started. Criteria 7's learning leg and 8's inductions remain untouched.
**⚠️ Corrected in S42: a merge to `main` does *not* deploy.** Both this file and PROGRESS.md said
it did, for several sessions. `deploy-staging.yml` is `workflow_dispatch:` only — the `push`
trigger is commented out on purpose ("not something that should fire unattended on every push
until it's been run and reviewed at least once"), and that comment has been overtaken by the six
reviewed runs since. Deploying is `gh workflow run deploy-staging.yml --ref main`. The trap is
that `gh run list --workflow=deploy-staging.yml --limit=1` happily returns the *previous*
successful run, so a check written to confirm "the deploy succeeded" passes against a deploy that
never happened — which is exactly what it did here before the head SHA was compared.
**⚠️ And `make e2e-staging` did not point at staging (AUD-F-17, fixed).** `E2E_TARGET=staging`
selects the auth path, not the browser's target — `config.ts` defaults the web URLs to
`localhost:5173`/`5174` regardless — so the suite ran against localhost and returned **2 passed,
everything else connection-refused**. Fixed in the Makefile. **Two false premises about this one
criterion, both previously recorded as working**; a step called "the one thing left" should be
executed once before it is believed.
**⚠️ Criterion 2 cannot be met on the current ordering, and this needs a decision before it is
planned around.** It demands zero open P1s, but **AUD-L-07's remaining read half is explicitly
scheduled for S43/S46** — it needs the assignment/branch-roster model `ProfileAdapter` gains in S43,
and both sessions come *after* the gate. Two ways out, and it is a product call: (a) fail closed now,
refusing tutor/branch_manager *reads* of dashboards and reports too — cheap, but S40 already showed
this ends tutor report generation outright until S46; or (b) accept it as documented §7
residual risk and let S43/S46 close it properly. (b) is the recommendation: the exposure is a tutor
reading students they are not assigned to, in a system with no real users, and (a) removes a
shipped feature to satisfy a checklist item.
**7, 8 and 9 are undone but no longer blocked** — the "missing" staging token secrets
were always retrievable from Secrets Manager (D-107 §10), so the authenticated load run, the two
learning-app alarm inductions on their real condition, and an authenticated-traffic trace scan are
all now reachable. **1** is unassessed since S37.

### Sessions 42–47 — Integration readiness and implementation *(INTEGRATION_PLAN §3, §5)*
- **S42 — discovery, Tier 1 org asks, and the auth decision gate. ⚠️ NOT STARTED.** The session
  numbered S42 (2026-07-27, D-110) spent itself on Phase 0B P1s instead — the spine puts the gate
  *before* discovery, criterion 2 needed the P1s, and everything below is blocked on the org
  replying rather than on code. **This scope is fully outstanding and its asks have external lead
  time, so send them before the next session rather than at the start of it.** Exercise
  `POST /api/accounts/login`, `GET /api/accounts`, `GET /api/accounts/signups` server-side from
  AWS; icrest availability history; DB topology/network path/read-only account; DNS additions;
  live role-string survey, timezone convention, schema snapshot. **Selects the §3.1 auth option
  (O1 login-API delegation is the provisional recommendation) and the I11 data-path rung**,
  recorded with §7 residual-risk acceptance in DECISIONS.md before S44 implements.
- **S43 — `IcProfileAdapter`** (I3–I7, I15) behind the existing `ProfileAdapter` Protocol: id
  namespacing (`acct-<id>`/`child-<id>`), attendance derivation from `signups.attended`,
  fail-closed role mapping, branch enrichment; contract tests against captured fixtures + a
  deploy-time schema smoke probe (I12).
- **S44 — independent auth** (I1, I14): the selected option, token issuer with SPEC claims +
  per-app secrets, login UI replacing `DevLoginScreen`, per-account+per-IP login rate limiting,
  refresh/revocation, logout semantics.
- **S45 — consent** (I9, I10): ledger (external ids + enums only, no PII), parent-grants-for-
  child capture UI, age-band derivation, no-consent→no-token; legal text from the §6.1 track.
- **S46 — role scoping + frontend completion** (I2, I8): student/parent-only issuance, the
  formal D-086 disposition, entry/login/session UX end-to-end in both apps.
- **S47 — integration-specific test pass**: E2E against a production-schema replica seeded with
  realistic edge data (soft-deleted children, NULL attendance, unknown roles, unverified
  accounts, duplicate signups), auth abuse tests, staleness drill, PII re-audit of the new
  login path.

### Sessions 48–51 — Rollout *(INTEGRATION_PLAN §5, §6)*
S48 production environment (`terraform/environments/production`: multi-AZ, ≥2 tasks, deletion
protection, dev-token gates off, domains + ACM + additive DNS, alarms to a monitored inbox);
S49 real credentials + feature-flag audit (SES or email flag-off; Maps/Calendar/YouTube
real-or-off) and the live connectivity path; S50 A7 close-out (WAF, backup-restore drill, ZAP
on prod config, runbook updated for the integrated topology); S51 pilot start + graduated
rollout (allowlist → single-branch pilot → all branches → public chat).

**Dependency spine:** S35 → the four audits → stabilization → **gate** → discovery (S42) →
adapter → auth → consent/scoping → integration testing. Parallel: A6 real content (3 of 23
knowledge docs are real; curriculum is `linear_equations`-only authored, D-060) gates the
*pilot*; A7 gates *public* chat promotion, not the pilot; §6.1 legal docs gate the pilot.

### Parallel track (any time, non-coding) — Phase 0 legal & policy docs (§6.1)
Privacy Notice, AI Use Notice, product Learning Notice, retention policy, etc. Drafting can
happen in a writing-focused session; **counsel review is a launch gate, not a dev blocker.**
Also required before launch: real accounts/credentials from §5.35 (AWS, Google Cloud, GitHub
org, LangSmith, domains). The expansion adds two more decision gates that need sign-off
*before their sessions*, not at launch: the §5.30.1 payload widening (S21/S24) and the
team-member-names schema question (S17) — see plan §19.

---

## Dependency notes

- Sessions 2→3→4→5→6 are strictly sequential (all ✅).
- Session 7 needs 6; Session 8 is independent of 7 (can swap); 9 and 10 need 8; 11 needs 7+10. (All ✅ through S16.)
- **Milestone 4 (S17→S18→S19) is sequential within itself** but independent of Milestones 5–6 — it can interleave with the learning track for a change of pace. S17's test-debt cleanup, however, should land before S22/S24 multiply the HTTP-test footprint.
- **Milestone 5:** S20→S21 (hints need the canonical-content shape); S22→S23 (backend before frontend). S21 and S22 are independent of each other.
- **Milestone 6:** S24 needs S21 (chat's Hint intent dispatches to the ladder) and S22 (per-stage policy gate). S25 needs S24 (chat events) and S22 (finalize hook) — this is why memory moved from old-S17 to S25. S26 needs S22 and is better after S25 (memory enriches the narratives) but can ship before with score-only evidence. S27 needs only S20 (optionally, for misconception tags) and real YouTube creds for its live path. S28 needs S25 (memory/chat insights in reports) and S22 (accurate time data); a facts-only report could ship earlier if resequenced.
- S29 (multimodal) is independent — it can slot anywhere after S8; it sits in M7 to keep the expansion track uninterrupted.
- S30–S31 touch everything; do them after the features they instrument exist. S32–S34 are last.
- Real-credential caveat: S20/S21/S24/S26 LLM quality and S27's live sync are only *calibratable* once real Bedrock/YouTube credentials exist (D-025 posture) — every session stays buildable and testable against the mocks regardless.
