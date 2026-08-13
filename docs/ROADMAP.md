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

**⚠️ Correction 2026-08-03 (D-163): the "report numeric grounding" line above was never really
covered, and the gap was invisible.** It was satisfied by unit tests over `is_grounded` plus the
report service's own tests — but `MockBedrockProvider`'s report stand-in builds its text out of the
payload's own fields, so it round-trips the check **by construction**. Every test could only ever
pass, and the real deployed model failed the check **15 out of 15** times: the parent narrative had
been dark since S28 and no eval could have said so. Fixed in D-163, with
`scripts/measure_report_grounding.py` committed as the instrument that can actually answer the
question. **The transferable lesson for any future eval in this list: an evaluator whose fixture is
generated by the same deterministic stand-in it validates measures nothing.** Worth re-reading the
other expansion evals here against that test — hint leak detection has a real golden fixture and is
fine; memory ground-truth cases are worth a second look.

**⚠️ Second instance of the same class, one level subtler (2026-08-03, D-165/AUD-C-21).** D-163's
version was "the fixture is produced by the stand-in it validates". This one is: **the fixture is
produced *from* the thing it is measured against**. The §18-C3 access-probe fixture generates each
question from the corpus chunk it targets, which is a large improvement over hand-written cases
(it is what overturned a keyword rule that had scored 8/8 against questions written beside their own
answers) — but a generated question still sits *closer* to its source chunk than a real user's
phrasing does. So a similarity threshold tuned on it reads optimistic: 25/43 at ≤0.40 on the
fixture, and the fixture's own attendance case misses at 0.418 once you check the number directly.
**The generalisation for any future eval here: ask not only "who wrote the fixture" but "how close
is the fixture's input to the artifact it is being matched against, compared with a real user's".**
Mitigation used: record the measured `lexical_overlap` per case so the bias is visible in the
fixture itself rather than inferred later.

### Session 31 — Observability *(old S20, unchanged scope + carried caveats)* ✅ (done 2026-07-21)
**Spec:** §5.32, Phase 20 (§6.21)
**Build:**
- Structured JSON logging with the §5.32.3 PII denylist enforced by a log-schema test
- OpenTelemetry spans across FastAPI → LangGraph → gateway → DBs → tools under one trace_id
- LangSmith wiring with masking config; Prometheus `/metrics` with the §5.32.4 KPIs; Grafana dashboards as code
- Resolve the standing D-032 caveat (`?token=` SSE values in access logs) before real deployment
**Done when:** one request's full path is visible under a single trace_id locally (otel-collector + Jaeger in compose).
> ⚠️ **"env-gated LangSmith" means wired, and for weeks that was all it meant.** D-242 (2026-08-10)
> found the LangSmith half had **never delivered a single run** on staging: 403 on every flush,
> retried forever at WARNING, zero runs, and nothing alarming on it. Fixed by
> `LANGSMITH_WORKSPACE_ID` and now verified end to end. The OTel/X-Ray half of this block was
> always genuinely working. **Read "shipped" here as "the code path exists", not "the sink
> receives".**

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

> **✅ Phase 0B's audit backlog is empty as of D-183 (2026-08-05).** S40–S41 took "all P1s +
> cheap P2s" (below); the rest were dispositioned or fixed session by session. **0 findings are
> open** in [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) as of D-183 (2026-08-05); this line read
> "1 open — AUD-F-33" from D-181 until then, and "5 open — AUD-L-08, C-23, C-24, F-22, F-33"
> before that, and the paragraph below it had already
> been corrected twice, which is the argument for deriving the number with the `awk` rather than
> reading any sentence, this one included.
> With S43–S47 frozen and the backlog empty, post-gate sessions run out of PROGRESS.md's
> "Next session" pointer (product decisions and carry-overs) rather than under a numbered block.
>
> **The two decided-and-awaiting findings are implemented (2026-08-04, D-176), so the decided pile
> is empty again.** **AUD-F-22** (child resolves at login — the user picked "at login" over "at
> dashboard entry" when the recorded wording supported both) and **AUD-L-08** (declared item count
> as the denominator, out-of-range flagged `unmeasurable_out_of_range`, never clamped) are closed
> with tests. **D-177 (2026-08-04) then closed AUD-C-23 (floor 0.9 + pre-floor tier margin, chosen
> by re-measurement; live 10-probe re-verification owed after deploy) and AUD-C-24 (chat free text
> redacted at the request boundary), so the backlog is now 1 open**: AUD-F-33 — no longer deferred.
> **D-182 (2026-08-04) diagnosed it for $0 from read-only alarm history and applied the fix the same
> session**: the scale-in alarm reached ALARM through `treat_missing_data` with no metric *value*, so
> Auto Scaling refused every invocation and created no scaling activity, which is why two earlier
> sessions read the activity list and found nothing. Deterministic at 46 invocations, 0 exceptions.
> It stayed **open** because one row was owed — Auto Scaling had not yet been observed *accepting*
> the new metric-math alarm. **D-183 (2026-08-05) read that row on both services and closed it**:
> `set-alarm-state` → OK put each alarm one evaluation from a real re-entry, CloudWatch's own
> evaluation returned both to ALARM on the live `FILL(m1, 0)` series, and both invocations read
> `Successfully executed action` with `with_value 15` — the FILL signature (pre-fix acceptances
> never carried more than 3 values). $0 spent; services untouched at their floors.
>
> **⚠️ How to recount, corrected 2026-08-04 (D-174) — the previous instruction here was the one that
> produced a wrong number.** It said "derive the count from the table, never carry it forward",
> which is right in spirit and was insufficient in fact: the Index had **stopped being maintained**
> after AUD-F-20 / C-16 / X-08, so **27 findings had a detail section and no row** and a
> table-derived count silently missed them. That is how the post-D-173 pointer arrived at "8, 9
> counting AUD-F-16" while **AUD-F-22** and **AUD-F-33** (both P2, both open) were invisible and
> **AUD-F-16** had been fixed for two weeks.
>
> So: **recount by grep, and read *both halves* of the Index** — the original table *and* the
> "S43 and later" continuation block. Cross-check that every `### AUD-…` section has a row (D-174
> left that invariant holding, at 0 exceptions) and that no id appears twice (the `AUD-L-17`
> collision is resolved — D-159's P2 is now `AUD-L-19`). **A finding's body can also contradict its
> own status**, and the status wins: D-174 §3a lost time to a "not yet checked" bullet that was
> never struck when D-112 closed the finding.
>
> **One benign duplicate, so nobody re-investigates it (checked in D-178):** `### AUD-C-16` appears
> twice, and it is *one* finding with two sections — the original, plus a later
> `### AUD-C-16 (settled) …` that escalates it P3 → P1. Unlike the `AUD-L-17` collision, no
> renumbering is owed. A mechanical "no id appears twice" check flags it; that is the check being
> imprecise, not the file.
>
> **⚠️ The `awk` reads the status positionally, so keep `|` out of the first four cells.** Four rows
> already carry an extra pipe (AUD-C-14, C-15, L-16, F-16 — 8 fields where the norm is 7); checked in
> D-178, all four still have their real status in `$5` because the stray pipe sits in the *description*
> cell, after it. A pipe in the id, area, severity or status cell would shift `$5` and silently
> miscount that finding — the fourth way this count could go wrong, after the three already recorded.
>
> **⚠️ A naive `grep -i open` over this file now over-counts, and the fix is to anchor on the status
> column.** Several rows carry their own history *inside* the status cell — AUD-F-16's reads
> "✅ fixed … ; this row read `Open — before the gate` until 2026-08-04" — so the word appears in rows
> that are closed. Found immediately after D-174 shipped, by a recount that returned 7 and named
> AUD-F-16. Status is the **5th** pipe-delimited field and a real open finding *starts* with `Open`:
>
> ```
> awk -F'|' '$2 ~ /^ *\*{0,2}AUD-[A-Z]-[0-9]+/ { st=$5; gsub(/^[ *]+/,"",st);
>   if (st ~ /^Open/) { id=$2; gsub(/[ *]/,"",id); sub(/\(.*/,"",id); print id } }' \
>   docs/AUDIT_FINDINGS.md | sort -u
> ```
>
> That returns **0** as of 2026-08-05 (D-183; it returned 1 from D-181 through D-182) — the Phase 0B
> audit backlog is empty. D-182→D-183 is the case to remember for *how a finding actually closes*:
> D-182 found the mechanism and shipped the fix and the count did not move, because the decisive
> live row had not been read; D-183 read it (Auto Scaling accepted the metric-math alarm on both
> services, `with_value 15`, forced for $0 with `set-alarm-state`) and only then did the count go to
> 0. **Diagnosing a finding does not close it, and neither does shipping a fix whose verification is
> owed.** The four entries before it are worth
> reading together — D-178 filed C-25, D-179's fix for C-25 found C-26, D-180 fixed C-26, and D-181
> filed *and* closed C-27 in one session — because the count went **up twice on the way down**, and
> each step came from building or running an instrument rather than from reading the code more
> carefully. (It returned 6 when
> this instruction was written, 5 after D-175, 3 after D-176, 1 after D-177, 0 after D-183.)
>
> **A finding can also be filed and closed without ever appearing in this count** (AUD-C-27, D-181).
> That is not the count hiding work: the row and the detail section both exist, and the arithmetic
> line in AUDIT_FINDINGS.md carries the `+1 −1` explicitly. Do not "reconcile" a same-session finding
> by deleting its row. **Do not "correct" the count to whatever a looser
> grep reports** without checking where the word sits — that is the same class of error twice over.
>
> Note that the count can go **up** without anything regressing: AUD-C-25 was filed by D-178 while
> *landing* D-177, from reading the shipped rule against the harness whose table justified it. A
> backlog that only ever shrinks is a backlog nobody is reading.
>
> Note also that *Open* and *Decided* are different piles: a finding whose fix has been decided but
> not implemented (AUD-L-03, AUD-L-09) is not in this count and is not done. That pile held AUD-F-22
> and AUD-L-08 from D-175 §5 until later the same day — **both implemented in D-176**, so it is
> empty again. (The pattern held: while decided-but-unshipped, they stayed `Open` in the table and
> were counted once, as open, with the decision recorded in the decision log rather than the status
> column.)
>
> **Take clusters, not findings — but the two clusters taken so far cohered differently, and the
> difference is worth carrying forward.** D-155 (AUD-C-07 + AUD-C-08 + AUD-C-10) was *one defect at
> three layers*: the three shared a missing concept, and fixing any one alone would have swapped a
> crash for a lie or a lie for a hang. D-156 (AUD-C-19 + AUD-L-13 + AUD-L-15) was *three defects of
> one shape* — a number or sentence shown to a family that the system could already have checked
> against something it knew — and they were taken together for the shared fix vocabulary, not
> because one was load-bearing for another. Both worked; the second is the more available pattern,
> since a backlog rarely offers a second three-layer defect.
>
> **A third shape, from D-169/D-170: a cluster can be right about the shape and wrong about the
> work.** AUD-L-12 and AUD-C-09 were taken together as "the masked-by-uniform-data pair" — correct
> code, never wired, invisible because the data has one value — and that reading held. But they
> closed by *different means*: one was implemented, and one turned out **not to apply at all** once
> the user was asked whether the corpus even has the dimension the SPEC predicate filters on. So
> pair findings by shape to get the vocabulary, and still ask of each one separately whether it
> describes a defect. A shared shape is a reason to read them together, not evidence that both need
> code.
>
> **A cluster can carry a product decision, and that decision belongs to the user, not the
> session.** D-156 surfaced two (should mastery include the post-exam; should two subsystems keep
> two definitions of "weak") and both were answered toward the larger behaviour change. Naming them
> before implementing is what kept them from being settled by a code comment.
>
> PROGRESS.md names the remaining candidate clusters. **One is not fix-ready: AUD-L-14 needs its
> evidence re-measured in a browser first** (D-107's run contradicts its headline number), and that
> is Playwright, which cannot run alongside `make test` on the shared dev Postgres.
>
> **A cluster's proposed fix is a hypothesis until the code is read.** AUD-F-37 was filed with a
> one-line Terraform fix that turned out to reverse a deliberate, documented exposure decision; the
> real fix was two gates in the deploy workflow and touched no infrastructure (D-158). Check whether
> something is absent *on purpose* before adding it back.
>
> **And a fix is a hypothesis until the test measures the effect.** D-159's AUD-X-03 guard was
> written into `flow.select_topic`, a function with **no callers** — the live path is
> `graph/nodes.py:select_topic`, which reimplemented it. Only a test asserting *row counts* caught
> that; a status-code assertion would have passed. Two corollaries worth carrying: read the path
> that actually runs, and prefer assertions on rows, spend and checkpoint counts over response
> codes, since every finding in this cluster returned a 200 or a plain 500.
>
> **A finding's write-up can go stale between filing and fixing.** AUD-X-03 blamed a hardcoded
> `busy={false}` that AUD-F-27 had already fixed. Correct the record in place (D-158's convention)
> rather than quietly re-scoping.
>
> **A threshold measured only in the direction it helps is half-measured (D-172).** All three
> findings in that cluster were "a guard whose floor is lower than its name", and two closed with a
> number that had to be chosen. In both cases the *buy* was easy to measure and the *cost* was not —
> and in both cases the cost measurement is what changed the design: "≥20 characters **or** the whole
> chunk" was rejected once the five sub-floor chunks turned out to be content-free headings, and the
> retrieval floor sits at 0.35 rather than 0.50 because the answerable tail is the one a fixture
> under-measures (D-166's live lesson). A threshold justified by its buy alone reads as
> equally well-evidenced and is wrong in the direction users notice.
>
> **Two more from the same session, both about instruments rather than code.** A test double can share
> a scale with the real model and measure a different quantity — `MockBedrockProvider`'s reranker
> returns query-word coverage on 0-1, so applying a real-model floor to it moved a gated category by
> 11 points with nothing broken; check what a number *means* in the double before comparing it. And
> **an opt-in paid instrument stops being evidence the moment it stops being run**: the real-Bedrock
> coverage eval had been failing since D-168 landed and only D-172's verification found it, which is
> AUD-F-15's shape (`chat-purge` had never once run) on a test rather than a job. The cheap fix is a
> bounded arm — `CHAT_EVAL_CATEGORIES=no_answer` is **10 cents and 72 seconds**.
>
> **A cluster can also be wrong about its own size, and a combined heading is how (D-173).**
> AUD-F-03/F-04/F-05 were taken as three findings of one shape ("frontend state that should derive
> from the persisted snapshot"). The shape held for two. **AUD-F-05 had already been closed by
> AUD-F-21** — the fix is described in a comment that names the finding's own mechanism, and a
> regression test written to its subject was already passing. It read as open because F-04 and F-05
> share a single heading in AUDIT_FINDINGS.md, so one status column covered two findings. That same
> heading shifted **every** `AUD-F-0x` reference in `e2e/` by one against the table. Two rules:
> **file one finding per heading**, and **read the code before implementing a fix** — this one was
> already written. Together with D-170 (a shared shape, one finding inapplicable) the general form
> is: a shared framing earns two findings a joint *reading*, never a joint *verdict*.
>
> **A deterministic build makes a frontend deploy verifiable by identity, not by grep (D-173 §7).**
> D-157 §2 confirmed a frontend deploy by grepping the deployed bundle for a class name and called
> that "luck, not design". The better use of the same property: **build the commit locally and compare
> bytes.** The deployed bundle and a local build at the merge commit matched on filename, size and
> SHA-256 — which answers "is this commit live?" outright and also proves the S3 sync ran. Prefer it
> to a grep whenever the build is deterministic; its limit is that it proves correspondence to a
> commit, not that the commit is right.
>
> **And a fix can be verified live by a probe whose real job was something else (D-173).** The
> control run to prove that AUD-C-23's `access_hint: null` was a real negative rather than an empty
> corpus happened to be the exact question D-166 had recorded returning the *wrong* tier — so it
> doubled as a live before/after pair for AUD-C-22's fix, from the record rather than from a test.
> Worth noticing when choosing a control: prefer one whose expected value is already written down
> somewhere.
>
> **And a *negative* result is a hypothesis until the control could have been positive (D-171).**
> "Zero `access_probe_rerank_degraded` events" was paired with a control grep for `access_probe`,
> which also returned zero — and was worthless, because that substring appears in exactly one log
> statement: the degraded branch itself. The zero was fully compatible with the probe never running.
> The control that worked came from a different mechanism than the signal (**request counts**), which
> is the transferable part. Together with D-159's caller-less guard, D-102's concurrent arm and
> D-157 §2's smoke test, that is **four checks in this backlog that passed while measuring nothing** —
> so "what would make this check fail?" is a standing question, not a flourish.
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

**✅ THE GATE IS CLOSED (2026-08-01, D-148, on the conditions recorded there).** D-144 fixed
AUD-C-17 and criterion 4; D-147 re-met criterion 3 (two clean whole-suite staging runs, first
attempt); D-148 closed criterion 6 early by user decision on a real one-off Scheduler firing, with
the 08-02/08-03/08-05/08-09 scheduled firings as reopening-capable confirmation reads; D-149
proved the weekly cron path with a throwaway clone, leaving only the `SUN` enum value to 08-02.
Next scope is **S42 discovery**, gated on the org replying to Message A (unsent). Post-gate
session D-150 closed the remaining pointer P2s (AUD-C-18 root-caused, fixed and live-verified
15/15, AUD-X-16's `make tfvars-floor-check`, AUD-F-35's evidence bar) — deployed same day as
`gha-812db34916a6` by user decision, de-risked with a clean manual consolidate run on the new
image (D-150 §5); none reopen a criterion.

*(Superseded, 2026-08-01 first half — fixed by D-144 the same day:)* **⛔ Criterion 4 (green full
test runs) is BROKEN as of 2026-08-01T00:21Z, and criterion 2 gains a P1
(D-143).** `make test` went red **at a date boundary with no code change**: eleven `rag_documents` carry
`effective_from = 2026-08-01T00:00Z`, the effective corpus went from 3 documents to 14, and
`adversarial` fell 100% → **66.7%** against a **1.0** threshold. **AUD-C-17 (P1)** — the containment
assertion had been passing by having nothing to retrieve, which makes every prior green on it vacuous.
Also **AUD-X-16 (P2)**: `*.tfvars` is gitignored, so the checklist step that has failed three times is
in an untracked file. **No criterion may be claimed while the suite is red.**

**✅ The `terraform apply` prohibition is retired (2026-07-31, D-142).** The user lifted it, the floor
was bumped `544c6fe → cfe9dbc` **first** — a bare apply would have made the pre-AUD-F-34 image the
ops-task family's revision, and the schedules resolve that family un-pinned — and the apply is done.
`terraform plan` is clean *and* agrees with the running image. Criterion 6's date is unchanged at
**2026-08-09**: the window was disturbed four times today, but a strict restart puts the purge jobs at
08-07 while `memory-consolidate`'s second firing binds at 08-09 (D-114 §3).

**⛔ Criterion 3 is NOT met as of 2026-07-31 (post-D-141 §9), and criterion 2 has two new P2s.** The
post-deploy re-run produced one clean whole-suite run (53 passed / 4 skipped) and **one failure** —
`journey-parent.spec.ts:17`, same image, no deploy between, so not a regression. **AUD-F-36 (P2)**: a
parent's child-selection interrupt hangs forever when `/respond` beats the SSE subscription (passing
record: stream open 178 ms before respond; failing record: same millisecond). ~1 in 3 whole-suite runs,
0 of 3 in isolation. **Criterion 3 is owed two consecutive clean runs, behind a P2 that makes any run
~⅔ likely to pass — re-running until two land clean would be claiming it by selection.** Criterion 2
now carries **AUD-F-35** and **AUD-F-36**.

**✅ Standing as of 2026-07-31 (post-D-141): AUD-F-34 is fixed, deployed and verified — criterion 6 is
unblocked but not yet evidenced.** `memory-consolidate` had its first clean run ever on
`gha-cfe9dbc0d507` (ops-task rev 40): **8 of 8 calls succeeded, exit 0, 5 facts reconfirmed**. So
2026-08-02's firing is now a real test rather than a guaranteed failure. **The date still rests on the
two-firing reading chosen this session: 2026-08-09.** Criterion 2 is affected: AUD-F-34 closes, and
**AUD-F-35 (P2)** is newly open. Read criterion 6 with `make scheduler-evidence`, which now also fails
its verdict on failure lines regardless of exit code, so it cannot certify a hollow run.

*(Superseded, post-D-140 — the analysis stands, the blocker is cleared:)* **criterion 6 is blocked on a
P1 code fix, not on the calendar.** **AUD-F-34** — `memory-consolidate` has **never once worked**: every model call fails on
prompt length (`215355 tokens > 200000 maximum`) and the job **exits 0**, so the ops-task failure rule
(`exitCode: anything-but 0`) cannot fire and its own summary line reads `Consolidation run complete …
0 added`. Found by the de-risking run recommended in D-138 §6, **before** the job's first-ever firing.
So 08-02 would have produced a firing count, a work line, exit 0, no alarm — and a tick. **2026-08-09
is now only a floor**: a second firing would fail identically and look identical. Criterion 6's date is
unknowable until the fix lands and the job fires successfully twice, and the fix is application code, so
it ages criterion 3's evidence and needs the deploy D-137's prohibition protects — sequencing is a user
call (D-140 §5). Zero open P0/P1 (criterion 2) is also affected: this is a new P1.

*(Superseded, post-D-138 — the date correction below stands; it is simply no longer the binding
constraint:)* **the gate does NOT close on 2026-08-02.** `memory-consolidate`
**has never fired** — created 2026-07-27 02:48:30Z against a `cron(30 18 ? * SUN *)` UTC expression, so
Sunday 07-26's slot had passed 8h18m before the schedule existed; the metric has no datapoint at any
Sunday 18:30Z and the ops-task log group has zero `Consolidation` lines in its whole history, behind a
positive control. **08-02 is its FIRST firing, so D-135's "second firing" reading gives 2026-08-09.**
The other two jobs also move, measured from real creation times: `chat-purge` ≥7 days at **08-03**
(5 of 5 expected firings so far), `retention-purge` at **08-05** — where D-134 originally had it.
**The reading for a weekly job is an open decision** (two firings ⇒ 08-09, recommended; one successful
firing plus `chat-purge`'s week of the same mechanism ⇒ 08-02) and it is the *only* thing the date
depends on — D-138 §5. **Read it with `make scheduler-evidence`**, which is per job (D-114 §3) and
computes expected firings from each schedule's own expression rather than from anything written down;
D-135's per-job counts came from an inference, because `AWS/Scheduler` publishes no per-schedule
dimension at all.

*(Superseded, post-D-134:)* **1, 2, 3, 4, 5, 8 and 9 are met; 7 is met on a re-stated
target and now with a *measured* 0.7% margin; 6 is on the calendar (2026-08-02 / 2026-08-05) and is
the only criterion still open.** **Criterion 3 is met again**: two consecutive whole-suite staging runs,
**53 passed / 4 skipped / 0 failed** each, no deploy between them, against an image whose code is
**byte-identical to HEAD** (`git diff 544c6fe..HEAD -- apps/ packages/ curriculum/ knowledge-content/`
is empty). The `narrative-refresh.spec.ts` flake was diagnosed rather than absorbed — **it was the
test**, not the defect it probes (D-134 §5) — and the rewritten spec passed in both runs plus a third
targeted run.
**Criterion 7's margin is now quantified and it is thin.** At the documented 25 concurrent on 2 tasks,
ALB p95 is **2.98 s against the deployed 3.00 s threshold**; at 2.5 concurrent per task it is 0.3 s.
So the criterion is met on its stated reading and has essentially no headroom — quote the margin with
the tick (D-134 §7).

*(Prior standing, post-D-133:)* **1, 2, 4, 5, 8 and 9 are met; 7 is met on a re-stated target
and did NOT improve when its cheapest lever was pulled; 6 is on the calendar (2026-08-02 /
2026-08-05); 3 has slipped back to needing one more clean run.** Two criteria moved in opposite
directions this session. **Criterion 8 is now MET at 4 of 4** (D-133) — the inbox was read and all
four alarms are confirmed reaching a human; it took three sessions and none of the delay was
technical. **Criterion 3 is no longer freely claimable** — this session's four staging deploys, one
touching deterministic-core code, aged D-120's two consecutive clean runs. One clean re-run exists
against the new image (53 passed / 4 skipped / 0 failed, with `narrative-refresh.spec.ts` flaky);
**a second consecutive run is owed**. Nothing regressed in the product; the evidence aged because the
artifact under test changed, which is the ordinary cost of deploying during a gate.

*(Corrected by D-138 — `memory-consolidate` had not "fired at most once", it had never fired at all, so
08-02 is its first firing and not its second. The mid-clock-addition argument for `retention-purge`
still holds on its merits; it was being applied to the wrong shortfall.)*
**So the gate now needs ONE date: 2026-08-02, read per job.** No open engineering, and no remaining
human action beyond that single read. **D-135 pulled 08-05 in to 08-02** on a stated reading —
`retention-purge` was enabled 07-29, four days into the clock, and treating it as a mid-clock addition
rather than a clock restart costs nothing because **the extra three days generate no information**:
staging's oldest data is 2026-07-22 against 90/365-day cutoffs, so the job logs `purged 0 rows` today
and will until ~2026-10-20.
**⚠️ 08-02 is a floor and no reading moves it**: `memory-consolidate` is **weekly**, has fired at most
once, and a weekly job cannot evidence a week of unattended operation before its second firing. That is
a missing observation, not a strict reading.
**⚠️ No `terraform apply` against staging before the criterion-6 read (D-137, and the window is now a
week longer — D-138 §2).** The schedules run the
ops-task family's **latest revision, un-pinned** (`task_definition_arn` has no revision suffix, by
design), and any apply here replaces **three** task definitions including `module.ops_task` — so an
apply would swap the image under criterion 6's own evidence window. That is D-129 §6's rule, and it
would cost the re-run D-133 already paid for on criterion 3. If an incident forces an apply, use
`INCIDENT_RESPONSE.md`'s `-target` form.

**⚠️ Quote this reading with the tick.** Criterion 6 will evidence *the schedules fire unattended and
the jobs execute cleanly against the real database*. It will **not** evidence that the retention promise
deletes correctly — neither purge job has ever deleted a row on staging and neither can until ~October,
so that rests on unit tests (D-135 §4).
*(Superseded, post-D-134: "two calendar dates, 2026-08-02 and 2026-08-05". Superseded, post-D-133:
"one more clean e2e run, and two calendar dates".)*

*(Prior standing, post-D-129:)* **1, 2, 3, 4, 5 and 9 are met; 7 is met on a re-stated
target; 6 is on the calendar (2026-08-02 / 2026-08-05); 8 is 2 of 4 confirmed and needs a human to
read an inbox.** Every criterion except 6 and 8 is now closed on written evidence, and the two that
remain need a calendar and a mailbox rather than work. **Three of the six "met" claims are met on a
stated reading rather than absolutely** — 1 (every requirement traced *or* dispositioned; T-02 is
dispositioned, not built), 2 (no P1 open *without a decision*; §7-R8/R9 are live exposures), and 7
(the pilot's documented 25 concurrent, not the criterion's original 150). Quote the reading, not the
tick.
*(Prior standing, post-D-123:)* **2, 3, 4 and 5 are met; 8 is met but for a human
confirmation; 6 is on the calendar; 7 is met on a re-stated target; 1 and 9 are the two that
nobody has finished measuring.** Read the per-criterion notes below before quoting that summary —
**2 is met on a written reading, not by having zero P1-severity exposure** (§7-R8/R9), and **7 is
met at the pilot's documented 25 concurrent, not at the criterion's original 150**, which is
carried as a priced post-pilot obligation. **1 has been unassessed since S37** and **9's trace scan
has only ever covered guest traffic** — the authenticated half is now reachable and was not run.
*(Prior standing, post-D-114:)* **5 met** (six consecutive clean pipeline deploys plus the
demonstrated auto-rollback; the "consecutive" ambiguity D-105 left open is settled — `73396c1` →
`c58d1fe` has no failed deployment between them on either reading). **6 is on the calendar,
read per-job (D-114 §3)**: earliest 2026-08-02 for the original two schedules, **2026-08-05**
for the `retention-purge` schedule (applied and ENABLED 2026-07-29). **4 is met**
(D-111: `chat-web` and `e2e-typecheck` CI jobs landed; AUD-F-08 closed).
~~**2 needs two more P1 halves**~~ **(✅ decided 2026-07-30, D-123 — both accepted as §7-R8/R9;
see the criterion-2 block below.)** Original: **2 needs two more P1 halves**: AUD-L-07 (read half
— but see the ordering note below) and AUD-X-07 (half), both with written dispositions. **D-115 added and closed two more P1s in one
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
**✅ AUD-F-28 fixed and the learning leg re-measured (2026-07-30, D-122). Two of its three legs now
pass at 150 concurrent; the p95 leg is a documented, priced capacity gap rather than an open
question.** Sized from a measured curve, not a guess: on the unchanged task, throughput was flat at
~5.8 req/s from 10 concurrent upward with latency growing exactly linearly (Little's law within 4%),
so p95 ≤ 3 s held only to ~8 concurrent — and the task turned out to be **0.25 vCPU** with the app
container declaring **no CPU share at all** beside a 128-unit otel sidecar. Applied to learning-api
only: `256/512` → `512/1024`, `min_capacity` 1 → 2, chat-api's ALB p95 step policy replacing CPU
target-tracking, an explicit 384-unit app share, and `unhealthy_threshold` 3 → 5 (**AUD-F-29**).

| leg at 150 concurrent | required | before | after |
|---|---|---|---|
| p95 | ≤ 3 s | 34.98 s | **17.73 s** ⛔ |
| error rate | < 1% | 12.06% | **0.04%** ✅ |
| tasks / autoscaling | ≥ 2, active | 1, never scaled | **2 → 3 in ~1 min** ✅ |
| target 5xx / conn errors / kills | — | 64×2 / 127 / yes | **0 / 0 / none** |

**The supported concurrency is 25** (p95 2.45 s and 2.51 s, 0 errors, measured twice warm), ~37 at
the 3-task ceiling. **Decision (user call, D-122 §3): 25 is the documented pilot target**; 150 at
p95 ≤ 3 s would need ~6× the capacity (~12 tasks, ~$216/month) and is carried as a post-pilot
obligation. The cheapest remaining lever is `select_topic`, the p95 driver in every run.

**⛔ That lever was pulled AND measured, and it does not move this criterion (2026-07-31, D-132).**
The staging before/after ran at 25 concurrent, 2 tasks on both arms. **AUD-F-31's fix is confirmed in
the quantity it claimed** — 49 → 9 SQL statements per `select_topic` (identical in 125/125 traces each
arm), SQL time in the request 1037 → 156 ms median, `select_topic` k6 median 2.37 → 1.23 s with
disjoint 5-run ranges. **And criterion 7's own threshold metric did not improve:**
`http_req_duration` p95 went from median-of-p95 2.72 s with **0 of 5 runs breaching** the 3 s
threshold to **3.31 s with 3 of 5 breaching**. Overlapping ranges at n=5 mean no regression is
claimed; the projected *improvement* is refuted.

**The reason is that the task is CPU-bound at 25 concurrent, not I/O-bound** (ECS CPU peaks 79–92%
before, 72–96% after). Removing round-trips cannot raise a CPU-limited throughput ceiling —
`flow_total` and answers/s are both unchanged — so the returned ~1.1 s reappears as queueing in the
answer phase (p95 2.56 → 3.42 s). **The supported concurrency is still the documented 25 and the
~$216/month capacity obligation is still OPEN**, now for a measured reason rather than an unmeasured
one. **Stop describing `select_topic` as the cheapest remaining lever — it has been pulled.**

**What criterion 7 actually needs next is AUD-F-32**, filed off this measurement: ~726 ms of every
answer request is neither SQL nor graph-node time, ×10 answers ≈ 7.3 s of a ~15 s flow, and that is
what the p95 is now made of. It is a CPU/overhead question. **Size it before optimising it** —
D-132 §3's lesson is that `select_topic` was the biggest span in the profile and the wrong target,
because the profile could not show which resource was scarce.

**⚠️ And the ~$216/month figure quoted throughout this block prices compute only (D-133).** The
Fargate arithmetic is exact — 12 × $18.02 — and its linearity is measured rather than assumed. But
Postgres is `db.t4g.micro` with `max_connections` **~112**, and 12 learning tasks alone need ~252
connections by pool arithmetic (~21/task), ~315 with chat-api at its 3-task ceiling. **Over 2× the
ceiling**, so 12 tasks requires resizing RDS too and **~$216 is a floor, not a total**. Two questions
come before the money: **150 concurrent has never been validated as a requirement** (it is §6.23's
number, not measured demand, against a documented pilot target of 25), and **AUD-F-32 is the
CPU-per-request lever** that could roughly halve the task count. **Purchase deferred (user call,
D-133); re-price after both, and include the database.**

**✅ Re-priced 2026-07-31 against a ratio, and the two paragraphs above are now superseded in both
halves (D-136).** AUD-F-32 was measured (D-134: the gap is queueing) and the last CPU lever was sized
and rejected (**batching `submit_answer` saves 0.9 ms of ~20 ms, 4.6%**), so **there is no remaining
code lever that materially changes CPU per request** — the "could roughly halve the task count" hope is
gone, and capacity is bought rather than optimised. Interpolating ALB p95 between the only two measured
arms, `p95 ≈ 0.31 s × (r/2.5)^1.4` for `r` concurrent users per task (**not** extrapolable outside
r ∈ [2.5, 12.5]):

| target r | p95 | tasks at 25 | tasks at 150 |
|---|---|---|---|
| 12.5 (today) | 2.95 s | **2** | 12 |
| 7.5 | 1.44 s | 4 | 20 |
| 5 | **0.82 s** | **5** | 30 |

**The expensive target and the real target are not the same target.** At the documented pilot 25,
moving off the 0.7% knife-edge costs **three more tasks** (2 → 5, ~+$54/month), and the ~$216 was always
for §6.23's 150. **And the RDS half of the obligation shrinks to nothing for the pilot:** D-133's
~21 connections/task is a *per-task constant* sized in S34 for one process serving 150 concurrent, so
multiplying tasks multiplies idle pool capacity — with `pool_size ≈ target r`, 25 concurrent needs ~40
connections and **`db.t4g.micro`'s ~112 suffices**. 150 still needs a resize, at 1.6× not 2.8×, and
**that resize has lead time, not just cost**: this account rejected `db.t4g.small` outright in S32/D-084.
**Recommendation: target r = 5, sized for the pilot, separable from the 150 question** — which Message D
still decides. Nothing forces it; criterion 7 is met at 25 on its stated reading.

*(Superseded — how this read after D-131 and before the measurement:)*
AUD-F-31 is fixed: the build issues **7 SQL statements instead of 47**, and ~40 fewer round-trips at
the ~32 ms each measured at 25 concurrent projects to most of the 1.62 s span that dominates the p95.
**Nothing about criterion 7 changes yet.** The supported concurrency is still the documented **25**,
and the ~$216/month capacity obligation is still open, because the evidence is a local statement count
plus a projection — not a staging before/after. **What closes this: a k6 run at 25 concurrent before
and after the change deploys, plus an X-Ray re-profile of `langgraph.select_topic`.** Only then can
the ~$0 fix be said to have replaced the ~$216/month purchase; until then it is *probable*, which is
the word this criterion exists to disallow. *(D-132 ran it. The caution was right and the projection
was wrong: ~$0 did not replace ~$216/month.)*
*(The original finding, kept because the before/after is the useful part:)*
**✅ Criterion 7's learning-app leg is measured (2026-07-30, D-121) — and it FAILS at the criterion's
own 150 concurrent (AUD-F-28, P1):** p95 **36.01 s** against ≤ 3 s, **13.16%** errors against < 1%,
`desiredCount` never leaving 1, ECS CPU at **99.88%**, and the task killed `(port 8001) is unhealthy`
mid-run. At 5 concurrent the same scenario is p95 **1.4 s / 0.00%** errors, so the flow is fine and
the capacity is not. The fix is a sizing/reaction decision needing the pilot's real expected
concurrency. **The chat leg remains met.** The same run also gave criterion 8 its first induction on a
real condition: `learning-api-p95-latency` OK → ALARM citing its own datapoints, SNS email confirmed.
*(Historical note below: this leg had been unmeasured since S34.)*
**Criterion 7's learning-app leg was unmeasured** under authenticated load (the staging
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
**✅ CRITERION 3 IS MET (2026-07-29, D-120): two consecutive clean runs against live staging**, both
**53 passed / 0 failed / 4 skipped** on build `447d412617a2` with the identity asserted, **zero
console errors and zero page errors** across 52 tests, and the only `serverError` being the 500
`response-shapes.spec.ts` stubs on purpose for AUD-C-10. The 4 skips are deliberate target scopes with
written reasons. It took five findings — AUD-F-21, AUD-F-24, AUD-F-25, AUD-F-26, AUD-F-27 — and only
the last two were what the failures actually were.

**The history below is kept because the wrong turns are the useful part.**
**⛔ Criterion 3 could not be claimed for a long time, and the reason changed twice before it was understood.**
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
**✅ CRITERION 2 IS MET on a written reading (2026-07-30, D-123) — the decision below was made,
and it is (b).** The two remaining P1 halves are now **accepted residual risks §7-R8 (AUD-L-07's
read half) and §7-R9 (AUD-X-07's mid-interrupt seam and commit ordering)** in INTEGRATION_PLAN.md,
each with an owner, a named closure, and an expiry condition. **The reading matters and is recorded
so nobody inherits it wrong:** "zero open P0/P1" is met in the sense that *no P1 is open without a
decision* — two P1-severity exposures still exist and are written down, R8 expiring at first real
traffic and R9 void the moment `learning_checkpoint_repairs_total` moves off zero. That is a
weaker claim than "no P1-severity exposure exists", and the roadmap's own standing caveat still
applies on top of it: **"zero open P1s" only ever measures what has been found** — D-115 found and
closed two P1s that had been invisible during every prior assessment of this same criterion.
*(The decision as it stood, kept because the argument is the record:)*
**⚠️ Criterion 2 cannot be met on the current ordering, and this needs a decision before it is
planned around.** It demands zero open P1s, but **AUD-L-07's remaining read half is explicitly
scheduled for S43/S46** — it needs the assignment/branch-roster model `ProfileAdapter` gains in S43,
and both sessions come *after* the gate. Two ways out, and it is a product call: (a) fail closed now,
refusing tutor/branch_manager *reads* of dashboards and reports too — cheap, but S40 already showed
this ends tutor report generation outright until S46; or (b) accept it as documented §7
residual risk and let S43/S46 close it properly. (b) is the recommendation: the exposure is a tutor
reading students they are not assigned to, in a system with no real users, and (a) removes a
shipped feature to satisfy a checklist item.
**✅ Criterion 8's four alarms are all induced (2026-07-30, D-122 §4–5), three on genuine
conditions:** `learning-api-5xx-rate` (18:26:40Z, real 5xx from two deliberately pre-fix 150-runs),
`learning-api-p95-latency` (again, on this session's load), `chat-api-p95-latency` (19:17:56Z citing
`29.56, 34.08, 33.23 > 20.0` — proving AUD-X-13's *new* 20 s threshold is still reachable by real
degradation), and `chat-api-5xx-rate` via `set-alarm-state`, **recorded as synthetic**. The SNS email
subscription is confirmed. **What is owed is human**: confirming the four emails arrived in the
monitored inbox. Two notes for whoever re-runs this: D-121's "2 consecutive minutes" reading of the
5xx alarms is **wrong** (they fired on datapoints three empty minutes apart — CloudWatch evaluates
the last N datapoints that *exist*), and the chat induction **cost $17.25** in real Bedrock calls
because a threshold set 25% above the normal p95 takes four runs to straddle successfully.

**✅ CRITERION 9 IS MET (2026-07-30, D-129) — and it was met by ordering, not by effort.** The
authenticated load run, the trace scan and the log scan happened **in one session**, which is the
whole trick: D-121/D-122's authenticated traffic aged out of X-Ray unscanned because the scan came
later, and every trace scan before this one covered guest traffic only (D-104).

| store | evidence | result |
|---|---|---|
| traces | `make scan-traces HOURS=1` over the run window | **CLEAN** — 2,747 traces / 21,234 segments / 1,568,546 strings, positive control **20/20** |
| — coverage | 350 authenticated traces in the window, = the run's 350 requests exactly | the interesting data was **in** the scanned set |
| logs | new `make scan-logs`, same patterns and matcher | **CLEAN** — 495 events pinned to the run window; **CLEAN** again over the surrounding hour (2,774 events / 58,054 strings) |
| metrics | no custom CloudWatch namespace exists at all; Prometheus labels are bounded enumerations + a *templated* route path, and `/metrics` is not routed at the edge (returns the SPA) | no app-controlled dimension can carry an identifier |
| payloads | no store holds them by design; the scans would have caught an echoed name or prompt in either store | nothing observable to leak |

**The reading, stated because criterion 9 is easy to over-claim:** this is *zero PII found by a
positive-controlled detector over a corpus proven to contain authenticated traffic*, in the two
stores that actually record request data. It is not a proof that no PII can ever reach them — D-104
§4's rule stands, that a floor is per-store and re-opens whenever instrumentation is added.
**The log half had no repeatable tool until this session**; it rested on S38's one-off CLI pipeline
over guest traffic, which is the weakest evidence in the gate and nobody had noticed because the
sub-item read as done. [scripts/scan_logs_pii.py](../scripts/scan_logs_pii.py) fixes that, and its
four failure modes were control-tested in both directions (truncated slice → FAIL, unreadable
window → FAIL, zero events → FAIL, a configured log group that no longer exists → FAIL, clean
corpus → CLEAN).
**Two findings came off the same run — AUD-F-30 and AUD-F-31.** AUD-F-31: `select_topic`'s 1.6 s is
**51 sequential SQL statements and no model call**. It read at the time as criterion 7's remaining
p95 gap having a ~$0 fix that the ~$216/month capacity estimate was hiding.
**Both are now fixed and measured (D-131, D-132), and the "~$0 fix" reading was wrong.** AUD-F-31's
statement count is confirmed on staging (**49 → 9**, 125/125 traces each arm) and criterion 7's
threshold metric **did not improve** — the task is CPU-bound at 25 concurrent, so removing
round-trips moved the queueing instead of removing it. **The ~$216/month obligation stays open**, and
the successor target is **AUD-F-32** (~726 ms per answer request that is neither SQL nor graph work).
AUD-F-30 is fixed the same session, after the measurement rather than with it (D-129 §6).

**✅ CRITERION 1 IS MET (2026-07-30, D-129) — the one sentence got written.** T-02 is dispositioned:
**S45 builds §5.1.2's first-visit notice; the §6.1 legal-and-policy track enumerates the eleven
disclosures first**, in that order, because a notice drafted from an implementer's reading of the
spec is how it ends up disagreeing with the policy it summarizes. Both clauses now hold — 37 of 37
sections mapped, zero open discrepancies. **Met the way criterion 2 is met (D-123):** nothing is
undecided, which is weaker than nothing is missing. T-02 is scheduled, not shipped.

*(How it stood one session earlier:)*
**▶️▶️ Criterion 1 is swept end to end — 37 of 37 sections — and now turns on one sentence
(2026-07-30, D-128).** Its two clauses split: "100% mapped to implementation + test" is **satisfied**;
"every discrepancy dispositioned" is **not**, because **T-02 is open** (§5.1.2's first-visit notice,
owned only by implication). That disposition is a scheduling call, not a build. Tranche 6 also added
a fourth verdict, **structural**, for requirements naming an artifact rather than a behavior —
fenced by a mandatory enforcing mechanism, with §5.3 and §5.36 recorded as *descriptive* because
nothing mechanical breaks if their description drifts.
*(How it started:)*
**▶️ Criterion 1 is started, has an artifact, and is no longer undefined (2026-07-30, D-124).**
[TRACEABILITY.md](TRACEABILITY.md) supplies what it had always lacked — a **denominator**
(§5's 37 sections / ~197 subsections, minus §5.17 per D-078, §5.30.3's EKS-only controls per D-004,
and WAF per D-087) and an **evidence rule** (traced needs implementation *and* a falsifying test;
unverified counts as not traced). **Tranche 1: all ten non-negotiable rules traced, §5.25 and §5.30
swept whole — 2 of 37 sections. Not met, and not claimed.** It found **T-01**: §5.30.3 requires
**GuardDuty and CloudTrail** and neither appears in any decision in the repo, where WAF is equally
absent but dispositioned — a gap invisible to every other criterion, since no test fails and no
alarm fires. Estimate for the remainder: **two to three focused sessions**, mechanical, needing no
AWS and no spend.
**7, 8 and 9 are undone but no longer blocked** — the "missing" staging token secrets
were always retrievable from Secrets Manager (D-107 §10), so the authenticated load run, the two
learning-app alarm inductions on their real condition, and an authenticated-traffic trace scan are
all now reachable. **1** is unassessed since S37.

### Sessions 42–47 — Integration readiness and implementation *(INTEGRATION_PLAN §3, §5)*

> **⛔ DEFERRED BY USER DECISION (D-152).** The existing system stays as-is and **integration
> happens much later**: the plan is to finish and test this codebase against the dev fakes first.
> **S43–S47 are frozen by choice, not blocked** — do not start them, do not measure AWS→icrest
> reachability, do not finalize the auth option, and do not rewrite the dev fake (the
> `ProfileAdapter` Protocol is SPEC-derived, so the schema mismatches stay behind the seam).
> S42's *source* half is done (D-151); the rest waits for the user to say integration is starting.
- **S42 — discovery, Tier 1 org asks, and the auth decision gate. ⏸ SOURCE HALF DONE
  (2026-08-01, D-151).** The user made the production system's source available at
  `../IntelliChoice-web`, so discovery was answered from source rather than org recollection:
  **[S42_DISCOVERY.md](S42_DISCOVERY.md)** (8 readers → synthesis → adversarial verify; 8/10
  claims confirmed, 2 refuted-with-correction). **`GET /api/accounts/signups` carries per-child
  `attended`, so O1b is feasible and the DB path leaves the critical path** (I11 rung 1). Login
  and profile contracts, the full schema, the role vocabulary, and the timezone facts are all
  captured; INTEGRATION_PLAN §1's four schema claims verified.
  **Answered 2026-08-02 by the user (D-153), so the outstanding list shrank:** DNS is available
  (added at integration); the **timezone question is closed by evidence** — the published schedule
  is Mon–Fri 10:00–12:00 / 18:00–20:00, and the two conventions diverge only for Sunday evenings
  and 00:00–01:00 starts, so they produce identical dates and weeks; peak concurrency is
  unmeasured but the planning assumption is **~1,000 students across a week**.
  **Still genuinely org- or runtime-only, and all deferred with the integration (D-152):**
  TLS/proxy topology + outage history + where stdout goes (Message C), the from-AWS reachability
  measurement, and three live-DB reads (`SELECT DISTINCT role`, `SHOW CREATE TABLE` for drift and
  password collation, deployed-build confirmation). **The §3.1 auth selection and I11 rung are
  recommended (O1b, O2 as fallback) but NOT decided** — they need §7 residual-risk acceptance in
  DECISIONS.md before S44 implements, and that decision waits for the reachability measurement.
- **S43 — `IcProfileAdapter`** (I3–I7, I15) behind the existing `ProfileAdapter` Protocol: id
  namespacing (`acct-<id>`/`child-<id>`), attendance derivation from `signups.attended`,
  fail-closed role mapping, branch enrichment; contract tests against captured fixtures + a
  deploy-time schema smoke probe (I12).
  **⚠️ Scope known from D-151, to be handled *when S43 runs* (not before — D-152):** the MySQL dev
  fake models a system that does not exist — six structural mismatches (branch metadata columns
  production lacks; a role ENUM that cannot hold Tutor/Manager and is the wrong case; week-keyed
  attendance vs per-session tri-state; opaque external ids vs integer PKs; a parent-child join
  table vs an FK; grade `VARCHAR`/`str` vs INTEGER 0=K). Build `IcProfileAdapter` against
  production-shaped fixtures rather than extending the fake — S42_DISCOVERY.md §9. **Do not
  rewrite the fake in the meantime:** the mismatches stay behind the Protocol seam, and the live
  schema can still move under `sync({alter:true})`.
  **Design fact to plan for (D-152 §3): `IcProfileAdapter` merges TWO sources.** `BranchInfo`
  requires non-nullable `manager_email`/`address`/`latitude`/`longitude`; production `locations`
  has none of them — address and coordinates come from the new stack's own `org_branches`, and
  manager email from an `accounts` join on `locationId` where `role = 'Manager'`.
  **⛔ Security constraint (D-153 §5, rationale updated in §7): production `role` must never by
  itself grant an elevated role here.** The org's policy is that Student/Parent/Tutor are
  self-selected and `Manager` is admin-only — the frontend implements that, the API does not
  (`req.body.role` is persisted verbatim), and a fix has been requested. **The constraint stands
  regardless of that fix**: pre-fix rows may already carry a self-assigned `Manager`, production
  is frozen and schema-drifting, and authorization is not delegated to another system's input
  validation (CLAUDE.md rule 3). Map Student/Parent from production; gate `Tutor`/`Manager`
  behind an allowlist the new stack controls.
  **Also at S43 (D-153 §4): assert no ingested session starts 00:00–01:00 local or on a Sunday
  evening**, and log loudly if one ever does — that is the only window where the timezone
  convention could change which week a session belongs to.
- **S44 — independent auth** (I1, I14): the selected option, token issuer with SPEC claims +
  per-app secrets, login UI replacing `DevLoginScreen`, per-account+per-IP login rate limiting,
  refresh/revocation, logout semantics.
  **Added by D-167:** deleting `/dev/token` also deletes the `staging_token_shared_secret` setting,
  both `DevLoginScreen`s and their stored-secret keys, and the deploy probe's wrong-credential arm —
  so that probe needs re-pointing at the real login path rather than dropping. And confirm the new
  issuer **asserts** `sub` from verified credentials rather than accepting it from the request body:
  every per-student cost ceiling partitions on `sub`, so a caller-chosen `sub` makes those ceilings
  non-binding. That is safe today only because the endpoint is closed (D-167's measurement).
- **S45 — consent** (I9, I10): ledger (external ids + enums only, no PII), parent-grants-for-
  child capture UI, age-band derivation, no-consent→no-token; legal text from the §6.1 track.
  **Plus, assigned here by D-129 as T-02's disposition: §5.1.2's first-visit Adaptive Learning
  notice** in `apps/learning-web` — the eleven required disclosures, gated on the §6.1 track having
  enumerated them, following `LocationConsentModal.tsx`'s pattern for §5.1.3. It was owned only by
  implication until [TRACEABILITY.md](TRACEABILITY.md) went looking for it.
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
adapter → auth → consent/scoping → integration testing. Parallel: A6 real content — the
*knowledge* half (3 of 23 docs real) gates the *pilot*, but the **curriculum half now gates launch
(D-185, 2026-08-05)**, so it has its own track above and this parenthetical no longer states its
own scope; A7 gates *public* chat promotion, not the pilot; §6.1 legal docs gate the pilot.

### Parallel track (coding + authoring) — A6-C curriculum coverage *(D-185, 2026-08-05)*

> **⚠️ Promoted to a launch requirement by the user (D-185).** It previously lived as a
> parenthetical in the dependency spine ("curriculum is `linear_equations`-only authored, D-060")
> that gated only the *pilot*. It now gates launch.

**The measured position, counted 2026-08-05 — recount rather than carry forward:**

```bash
.venv/bin/python -c "
from collections import Counter
from intellichoice_curriculum.templates.linear_equations import LINEAR_EQUATIONS_TEMPLATES as T
print(Counter((t.skill_id, t.difficulty_label) for t in T))"
```

3 topics and 10 skills in the taxonomy; **50 templates, all `linear_equations`** (5 skills × 1 tier
× 10). `fraction_operations` and `place_value` have **zero**. Via `grade_topic_mapping.yaml` that is
**grade band 6-7 only**, on a K-12 product.

**Re-measured 2026-08-08 (D-222, extended D-223) — the count above is superseded on two of its
three claims.** `fraction_operations` now has **30 hand-authored, §5.8.5-gated items** spread
5/6/7/6/6 across tiers 1-5 and covering all three of its skills, and reports `available=True` and
`recommended_for_grade=True` for a grade-4 student. D-223 doubled it because the availability floor
of 2 per tier is a floor, not a target: at 3 per tier a 10-item pre-exam had to repeat at least half
of itself next session; at 5-7 per tier, three live exams covered 19 of 30 distinct questions.
**Every topic in the taxonomy is now stocked (D-225).** `place_value` was the last empty one and
has 25 hand-authored items, five at every tier across both its skills, weighted so `identify`
carries the low tiers and `compare` the high ones because the prerequisite requires it. Grade bands
served: **1-2, 4-5 and 6-7** — the K-12 span is no longer short at the bottom, though it is still a
three-band product rather than a twelve-band one, and grade 3 matches no band at all.

The count at the top of this block is now **obsolete rather than merely superseded**: it counted
50 *shape* templates, which `_servable()` had not served since D-210 and which D-226 deleted along
with the machinery behind them. The bank is 102 authored items — 47 + 30 + 25 — and every one of
them went through the deterministic gate but **not** the two-solver/judge panel (D-211), so they are
content, not calibrated content. Multi-tier for `linear_equations` (rule 2) is unchanged
and still inert.

**Not a live defect:** `topics.ts` no longer decides this at all (D-187) — availability comes from
the bank, so an unauthored topic renders "Coming soon" as a fact rather than a hand-maintained
flag, and the server degrades to `phase: "error"` rather than crashing if one is requested
directly. Coverage gap, not a break.

**Order of work, because the pipeline cannot produce this content as written:**

1. **✅ Answer the rule-2 question (product decision (a)) — done 2026-08-05, D-186.** The user's
   call: **multi-tier from the start, for the middle-difficulty skills.** `TOPIC_SKILL_DIFFICULTIES`
   records the plan — the three middle skills carry their native tier ±1, the ladder ends stay
   single-tier, and ±1 is the *whole* reachable range because `mastery_bootstrap` anchors
   `recommended_difficulty` at the modal tier ±1 and clamps to 1-5. 5 (skill, tier) pairs → **11**.
   It had to be answered first: authoring 1:1 would have kept rule 2 latent for the new topics too,
   and adding tiers afterwards is re-authoring rather than extending.
2. **✅ Unblock the generator — done 2026-08-05, D-186.** `generate_authored_candidate` takes an
   optional `skill_id` (omitted → derive from the tier as before; given → validated against the
   plan), and `run_authored_pipeline` iterates **(skill, tier) pairs**. The old loop derived the
   skill *from* the tier, so no number of runs could ever have produced two tiers for one skill.
   **Authored mode only:** `DIFFICULTY_SHAPES` is keyed by tier alone, so a skill generated at an
   off-native tier would draw another skill's math forms — the shape pipeline is untouched.
   ⚠️ `review_cli.rerun_with_edit` now carries `skill_id` from the superseded row; re-deriving it
   would have silently swapped the skill on the first multi-tier re-run.
> **Scope note, 2026-08-08 (D-226/D-227).** Two things below are now history rather than
> instructions. **The shape pipeline named in steps 2 and 3 no longer exists** — D-226 deleted it,
> along with its 50-template bank, because `_servable()` had filtered everything it produced out of
> every serving read since D-210, so "the shape pipeline is untouched" is no longer a caveat to
> preserve. And step 3's ⏸ is now **only** about multi-tier content from the *authored* pipeline;
> its versioned-home half was closed long ago (struck through in place below).
>
> **The track's measured position also moved past this block's framing.** Every topic in the
> taxonomy is stocked — **130 authored items across four topics** (127 until D-238 authored three more) — and grades 1 through 7 all
> resolve to one. D-228 authored `multiplication_division`, the topic §5.7.3's own 2-3 band names
> and the last hole in that range. **The coverage requirement's content half is met for the grades
> this product serves;** what remains is calibration and grades 8-12, which are scope rather than gap.
>
> **Calibration update, 2026-08-09 (D-229 to D-234).** D-211's two panels have now both been run
> over the whole bank, which had never happened. The **solver** panel agrees with the author on
> **127 of 127**, behind a 12/12 negative control — the situation-to-equation gap D-211 named is
> measured and, for this bank, empty. The **judge** took three sessions to make runnable at all (a
> shared token ceiling it could never complete under, a global timeout it sat exactly on, and a
> rubric written for `linear_equations` that graded four topics), and has now judged 125 of 127.
>
> Its result was **not** a clean bill: 25 items would have been rejected by the pipeline's own
> difficulty gate as it then stood, 24 of them the judge calling the item easier than declared.
> Either the hand-authored tiers inflated or the rubric's top anchors were unreachable; that pass
> could not separate them, and nothing was re-tiered on it. *(That gate no longer rejects on this
> criterion — D-239 changed it to re-tier the candidate to the judge's reading, gated on the judge's
> own dispersion. The sentence above records what the D-234 measurement meant at the time.)*
>
> **Settled 2026-08-09 (D-235 to D-237), and it was both.** Adjudicating all 25 against their
> topic's anchors: **12 upheld, 13 re-tiered** (16 items changed tier once three the gate never
> flagged are included; no item's *content* changed). Then the instrument half was tested rather
> than argued: measured over every tier-5 item in the bank, the judge returned **zero fives out of
> 17, twice, with an identical histogram**, while scoring 12-13/16 on an easy control — it was
> refusing the top of its own scale, not misreading the items. One prompt sentence fixed it, and
> re-judging the 12 upheld verdicts found **8 of 12 had become moot**.
>
> **Both weak topics diagnosed 2026-08-09 (D-238), and the two causes were unrelated.** The
> question left above — do those two topics' anchors discriminate in the 3-5 range — was answered
> by splitting the same data **per skill**, which is what made it legible. `place_value`'s rubric
> was two ladders in one coat: `place_value_compare` climbed 2.50 → 3.38 → 3.67 across declared
> 3/4/5 while `place_value_identify` sat **flat at every tier**, because tiers 4 and 5 each led
> with a bare digit-count clause — real work when you are ruling out places, none at all when you
> are reading one digit's place. `multiplication_division` was not an anchor problem: the skill is
> *"Divide with remainders"* and **all six of its items stated the remainder in the stem**, so no
> item exercised the skill it was filed under. Anchors split per skill, eight items re-tiered,
> three authored, six stems rewritten; both topics now pass the pre-registered discrimination
> criterion that neither passed before.
>
> **What is still unearned in this requirement**, and it is smaller than it was:
>
> - **Two rungs that do not separate**, both clause-level rather than item-level:
>   `place_value_compare` d4 (3.58) vs d5 (3.55), and `place_value_identify` d3 (2.35) vs d4 (2.12).
>   The pooled ladder is monotone partly *because* identify's low d4 items drag the pooled figure
>   down, so **never read this bank's calibration pooled across skills** — that is what hid the
>   original defect and it flatters the fix too.
> - **`difficulty_confidence` is still 1.0 by assertion** on all 83 hand-authored items. Nothing has
>   ever measured it; three sessions have now left it standing. It is the last unearned claim here.
> - ~~The three items D-238 authored have not been through the solver panel.~~ **Closed in the same
>   session, 5¢:** all five `place_value` tier-5 items pass the two-solver panel 5/5, behind a **5/5
>   negative control** — the script's own docstring is right that the first number means nothing
>   without the second.

3. **⏸ Ran 2026-08-05. The pipeline works and serving is built (D-188, D-189); the content is still
   not anywhere but one laptop.** The run produced eight items covering 7 of 11 pairs, five of which
   passed review — but approving them exists only as a row update in whatever database the pipeline
   was pointed at. CI proved it: the suite went green locally with them approved and **failed on CI**,
   whose database is seeded by `load_curriculum_and_templates` and therefore has none of them.
   **Authored content had no versioned home**, so there was no path by which a reviewed item
   reached staging or production. ~~That is the track's next step~~ — **done: approved items export
   to `curriculum/internal_math/authored/*.yaml`, which `loader.py` reads and re-validates on every
   load, in every environment** (`make question-export`; pinned by `test_authored_bank.py`, and
   `fraction_operations` reached staging by exactly this route in D-222/D-223). Struck through
   rather than deleted because this paragraph told two later sessions to build something that
   already existed. The remaining ⏸ below is about *multi-tier content from the pipeline*, which is
   a different thing and is still open.
   Serving them was the previous blocker and is now built: `build_variant_row` copies an authored
   template's canonical variant into a runtime row instead of rendering a shape it does not have.
   The post-exam **knowingly repeats** an authored item — SPEC §5.13.2 forbids reusing the same
   *variant* and a new row is still minted, the generated path already had this as a rare fallback,
   and each repeat is logged so the rate is measurable (D-189 §3).
   Four defects found by running it, all invisible against `MockBedrockProvider`, all fixed:
   the shared 400-token ceiling made authored generation **impossible** (measured: 631 tokens at
   tier 1, 954 at tier 5); the SymPy gate rejected correct answers written as `'x = 7'` or with a
   typographic minus, and was **quieter** for it (an unparseable distractor was exempt from the
   "no distractor also matches" arm); the judge scored 8–9 against 1–5 thresholds so the
   hint-quality gate **never fired**; and the seed formula made a second run collide with the first,
   which would have discarded the whole batch at commit. Spend: 24.8¢ across four runs.
   **⚠️ Multi-tier is still not met either.** The bank is one tier per skill and D-169's rule 2
   stays inert. Eight items covered 7 of 11 pairs, but the tiers
   differed by label more than substance (`2x + 5 = 19` at tier 1 vs `2x + 7 = 19` at tier 2)
   because `AuthoredGeneratorPayload` carries no per-candidate variation and no rubric for what a
   tier *means*. **Another paid run without that rubric produces the same result** — fix the
   generator before spending again.
   Four defects found by running it, all invisible against `MockBedrockProvider`, all fixed:
   the shared 400-token ceiling made authored generation **impossible** (measured: 631 tokens at
   tier 1, 954 at tier 5); the SymPy gate rejected correct answers written as `'x = 7'` or with a
   typographic minus, and was **quieter** for it (an unparseable distractor was exempt from the
   "no distractor also matches" arm); the judge scored 8–9 against 1–5 thresholds so the
   hint-quality gate **never fired**; and the seed formula made a second run collide with the first,
   which would have discarded the whole batch at commit. Spend: 24.8¢ across four runs.
   **⚠️ Multi-tier is still not met.** Eight items covered 7 of 11 pairs, but the tiers differed by
   label more than substance (`2x + 5 = 19` at tier 1 vs `2x + 7 = 19` at tier 2) because
   `AuthoredGeneratorPayload` carries no per-candidate variation and no rubric for what a tier
   *means*. D-169's rule 2 stays inert; the bank is still one tier per skill.
   *Original scope, retained:* D-026 forbids self-approval, so every item goes through
   `review_cli.py` — that is the cost driver, not model spend. Two gates push back on off-nominal
   tiers (reject a >±1 judge/proposed difficulty disagreement, flag exactly-1 as
   `review_priority="high"`), which is exactly the regime "a hard version of an easy skill" lives
   in — so **expect a higher rejection and high-priority rate on the six new pairs, as the gate
   working rather than a regression** (D-186 §5). Note `candidates_per_difficulty` is now per
   (skill, tier) pair, so the same value asks for more items than it used to.
   **⚠️ No content is authored yet, so rule 2 is still inert:** the bank is still 5 skills × 1 tier
   and `test_study_plan_difficulty_routing.py:132`'s canary still passes, correctly. D-186 removed
   the structural blocker and set the target; it did not move the bank.
   **Priced 2026-08-05 (D-187):** 4 LLM calls + 1 embedding per candidate, each capped at 2000 in /
   400 out; 11 pairs × 2 = 22 items → **~$1.06 worst case at the placeholder sonnet rates, ~$0.35
   at haiku**. Two prerequisites, both needing an explicit answer because `.env` is off-limits:
   `CURRICULUM_BEDROCK_PROVIDER` defaults to `mock` (and `.env.example` has no `CURRICULUM_`
   entries at all), and the default `anthropic.claude-sonnet-5` is not this account's invocable id
   (D-084's is `us.anthropic.claude-haiku-4-5-20251001-v1:0`). **The test that used to make this
   step break the suite is fixed** — see step 4.
4. **✅ Reconcile the two availability sources — done 2026-08-05, D-187.**
   `GET /learning/sessions/{id}/topics` serves availability from the template bank, using
   `assessment_builder`'s own threshold rather than a restated copy, and `grade_topic_candidates`
   is read at last through `CurriculumContent.topics_for_grade`. `recommended_for_grade` is
   conjunctive with `available`, so the grade map can never surface a topic the bank cannot serve —
   which is not hypothetical: every seeded student's band candidate is an **empty** topic today.
   `topics.ts` keeps only labels. Step 3's blocker also went with it: `test_loader.py` asserted
   `len(active) == 10`, so approving an authored template broke the suite (S20 hit this live); it
   now asserts identity, not size.

### Session C1 — Full-taxonomy content seeding *(D-273, planned 2026-08-11)*

> **One session, loop-until-done phases (the user's explicit structure).** The phases below run
> in order inside this single session; within a phase, iterate — generate → measure → fix the
> rubric/verifier → regenerate — until that phase's "done when" holds, then move on. Discoveries
> outside the active phase become PROGRESS.md carry-over, not detours. This track is independent
> of integration (S43+ stays frozen per D-152).

> **Reordered before any work, on evidence from prerequisite verification (2026-08-11).** The
> answer-model router (originally Phase 2, a family-B extension) now runs **before** seeding,
> because the gate does not merely fail to verify non-equation skills — it **reshapes them**.
> Measured: `place_value_compare` is **15 of 15** "how many more" subtraction word problems filed
> under *"Compare and order multi-digit numbers by place value"*; every other skill in the bank is
> 0/N. The cause is structural: for a skill whose answer is not *derived*, the gate leaves two
> moves — write `Eq(x, <the answer>)`, which passes while verifying nothing (D-191's defect in a
> relation costume; measured at 0 of 130 shipped items, so latent), or reshape the question until
> something is derivable, which is what these 15 did. The 34-book
> taxonomy is full of compare/identify/round/classify/order/read skills, so seeding first would
> propagate this across the whole taxonomy. **Volume target: D-223's measured 5–7 per occupied
> tier (~25–35/topic, ~1,000 items), deliberately diverging from SPEC §5.8.1's unmeasured
> 100/topic** — user decision, 2026-08-11, recorded in D-273.

**Goal.** Every row of `knowledge-content/intellichoice_math_topics.csv` (246 rows, grades 1–12)
is either **covered** — questions + hint ladders + canonical solutions in the authored bank, and
a video catalog entry where a suitable one exists — or carries an **explicit disposition**
(reshaped / needs-figures deferred / not-MCQ out of scope) in a coverage matrix. Along the way,
answer the pilot question the user actually asked: does the current pipeline generalize to the
whole taxonomy, and where it does not, build the specific extension rather than replacing the
pipeline.

**Structural decisions (D-273):** CSV **books → internal topics** (~40–50), CSV **rows →
skills** — "every row covered" means "every row is a stocked skill". The pipeline core
(generator → shuffle → deterministic gate → dedup → two solvers → blind judge → human review)
is kept as-is; what gets built is the verifier router (family B), figure support (family C,
own decision gate), per-topic rubrics at scale, and — evidence permitting — an auto-approval
slice for review throughput.

**Phase 0 — Coverage matrix + taxonomy design (free, no model calls).**
Triage all rows by **answer model**, which is the axis that actually decides pipeline fit:
**A** derivable single value (works today), **B** interval / tuple / multi-root / symbolic
(needs the router), **C** needs a figure, **D** not MCQ-able as written (reshape or
disposition). Map books→topics / rows→skills; design the full 12-band `grade_topic_mapping.yaml`
(mind the band-overlap trap pinned by
`test_adding_a_band_never_steals_a_grade_from_an_existing_one`).
*Measured facts to build on, verified 2026-08-11 rather than assumed:* the CSV is **34 books /
246 rows / 245 unique (grade, book, topic) triples** — `('6','Grade 6 Fractions','Three
Fractions')` appears twice — and only **194 distinct topic strings** ("Fractions" is in 7
different books), so a row is meaningful **only** as a triple and skill ids must be
book-qualified. Track coverage by triple, never by name; the honest denominator is 245.
Also: submit the third-Anthropic-model access request (Solver B independence,
QUESTION_GENERATION.md §6) or record the user declining it.
*Done when:* `docs/CONTENT_COVERAGE.md` exists with all 245 rows dispositioned by answer model,
the topic/skill mapping is user-reviewed, and the model-access question has an answer recorded.

> **✅ DONE 2026-08-11.** 245 unique rows → 34 topics → 245 skills; **A 173 / B 37 / C 34 / D 1**,
> pinned by 7 tests that fail if a row loses its disposition or the matrix drifts from the CSV.
> Mapping approved by the user as built. Model access **measured, not assumed**: three Anthropic
> agreements exist but only **two are invocable** — Sonnet 5 reports `AVAILABLE` and denies the
> call, and §6 had named it the intended premium Generator.

**Phase R — Answer-model router *(was Phase 2; moved ahead of seeding — see the note above)*.**
The gate today requires every item to be **one equation, one unknown, one solution**
(`derive_answer`, verified fail-closed on all six paths — it does *not* silently skip). Extend it
to a router over answer models, each with its own verifier: derivable value (existing),
**selection/comparison** (the answer is one of the stated objects — what `place_value_compare`
needed and never had), ordering, multi-root, interval, tuple, and symbolic equivalence. **Fail
closed:** an item whose answer model no verifier claims is a rejection, never a skip.
*Proof case, in scope:* re-author the 15 `place_value_compare` items so they exercise
comparison, and show the router accepts them where the old gate could not.
*Done when:* every verifier has both-directions tests (accepts the right answer, rejects a wrong
one — the D-246 lesson), the unclaimed-answer-model path rejects, `place_value_compare` measures
0/15 difference-shaped stems with the skill actually exercised, and the whole existing bank still
passes (`make test` green, bank re-load clean).

> **✅ DONE 2026-08-11 (D-273 Phase R outcome).** `multi_root` / `interval` / `tuple` /
> `symbolic` verifiers added behind `route_answer`, fail-closed, both-directions tested;
> `place_value_compare` re-authored **15/15 → 0/15** and re-gated through the loader (15 updated,
> 115 unchanged); two latent gate defects closed (the vacuous `Eq(x, 43)` form, and a
> `TokenError` that **escaped** the gate rather than failing it). All 130 shipped items still
> route as `value` and match their own key. **1214 passed**, lint and pyright clean.
>
> **The phase's premise was falsified before any code was written, and that is its main result.**
> `selection` was believed to need a verifier; `Eq(x, Max(34, 43))` derives 43 on the *unchanged*
> gate. Comparison questions were always expressible — so the 15-item defect is an **authoring**
> failure, not a gate limitation, and Phase 1's rubrics must teach the form rather than assume
> it is unavailable.

**Phase 1 — Seeding, one wave per grade band (K-2 → 3-5 → 6-8 → 9-12).**
Per wave: taxonomy files with **per-topic (per-skill where they differ — D-238) difficulty
anchors**, AI-drafted but human-owned and validated by the dispersion method, then
`make question-gen-preflight` → budget-capped `question-gen-authored` at ~10 items/topic →
`make question-review` (the user, item by item) → `make question-export` → PR. Iterate within
the wave — a failing topic usually means its rubric, not its items (D-238).
*Done when, per wave:* every A/B topic in the band has ≥10 approved items with every skill (CSV
row) stocked at ≥1 item and multi-tier where the skill spans; **each item's stem exercises the
skill it is filed under** (the D-238/Phase-R check, measured not asserted); judge dispersion is
real per topic (never pooled across skills); yield, human-rejection rate, and cost per accepted
item are recorded — these numbers are Phase 3's evidence.

> **⏸ PARTIAL — K-2 wave, 2026-08-11.** Taxonomy done; 54 items generated at 86% acceptance for
> **$1.51**. What holds and what does not, criterion by criterion:
>
> | criterion | result |
> |---|---|
> | ≥10 approved items per topic | **2 of 6** — g1_addition 13, g1_subtraction 10; the rest 8/8/8/7 |
> | every skill stocked ≥1 | ✅ **17 of 17** across all six topics |
> | multi-tier where the skill spans | **5 of 6** — `g2_word_problems` spans only tiers 1-3 |
> | judge dispersion real per topic | ✅ **6 of 6 discriminate** (dominant tier 25-75%, all under the 80% floor) |
> | stems exercise their filed skill | ⛔ **not measured on the new items** — the Phase-R check was run on `place_value_compare`, not here |
> | yield and cost recorded | ✅ 86%, ~3¢/candidate |
> | human-rejection rate recorded | ⛔ **N/A — review was skipped on the user's instruction**, so Phase 3's central number does not exist for this wave |
>
> The last row is the one that matters for sequencing: **Phase 3's auto-approval decision needs a
> human-rejection rate, and this wave produced none.** A later wave has to supply it, or the
> decision is made without its evidence.
>
> Three topics fell short of 10 because `candidates_per_slot` is 2 and a skill's tier span is
> deliberately narrow (D-223) — `g2_word_problems` has 3 skills over 5 tiers, so its plan
> schedules 10 and yielded 7. Raising `--candidates-per-slot` is the lever, not widening spans.

> **✅ 3-5 WAVE DONE — 2026-08-11 (D-275/D-276).** 7 topics, 26 skills, **160 items generated at
> 91% acceptance for $6.03**, 153 surviving to the bank. Every criterion but one now holds:
>
> | criterion | K-2 | **3-5** |
> |---|---|---|
> | ≥10 approved items per topic | 2 of 6 ⛔ | **7 of 7** ✅ (19/16/33/14/18/36/17) |
> | every skill stocked ≥1 | 17 of 17 ✅ | **26 of 26** ✅ |
> | multi-tier where the skill spans | 5 of 6 | **7 of 7** ✅ |
> | judge dispersion real per topic | 6 of 6 ✅ | **7 of 7** ✅ (dominant 28-42%) |
> | stems exercise their filed skill | ⛔ not measured | **partially** - the restored gate now
>   rejects an item whose equation does not model its own question, which is the mechanical half
>   of this criterion; 5 such items were caught on export |
> | yield and cost recorded | 86%, ~3¢ | **91%, ~3.7¢** ✅ |
> | human-rejection rate recorded | ⛔ N/A | **⛔ still N/A** - review was skipped again on the
>   user's instruction, so Phase 3's central number does not exist after two waves |
>
> **`--candidates-per-slot 3` was the lever, exactly as the K-2 entry predicted.** Tier spans
> were not widened and every topic cleared the bar.
>
> **What the wave cost in defects, and what it bought.** Five defects in the machinery
> (D-275) and one architectural one (D-276), all found by *reading output*, none by reading
> code. The most expensive to have missed: the pipeline had never run
> `check_sympy_independent_solve`, so **5 items with wrong answer keys were generated, approved
> and exported** before the bank's own gate caught them. Pipeline and loader now share one gate.
>
> **The bar for the next wave (6-8):** it starts with the gate the 3-5 wave ended with, so its
> yield is not comparable to 91% - a fair reading needs the *rejection* mix, not the headline.
> And it is the last chance to supply a human-rejection rate before Phase 3 has to decide
> without one.

> **✅ 6-8 AND 9-12 WAVES DONE — 2026-08-12 (D-277/278/280).** 12 topics, 51 skills, **201 items
> at 57% acceptance for $13.05**. Strong: `pre_algebra` 90%, `g6_word_problems` 100%,
> `geometry_measures` 80%. Weak and understood: `algebra_1` 4%, `algebra_foundations` 39%,
> `g6_fractions` 42% — all symbolic topics.
>
> **The after-action is the part worth keeping.** All 109 rejections were re-gated *offline*
> against the fixed parser, free, because D-195 stores candidate content with the rejection. The
> parser fixes recover 11 of 109 — so the low yields are **not** a broken gate, and a blind
> re-run would have spent ~$8 reproducing them. The remaining causes, measured: 43 answer keys
> disagreeing with their equation, 19 sentences over the readability ceiling (the rule is right,
> the content is wrong), 17 pairs of options equal in value, 7 hints stating the answer.
>
> A re-run of the six weakest topics with **D-198's repair path enabled** was in flight when the
> session ended — that is the lever for the mechanical defects, since the prompt already asks for
> what 19 items ignored.

**Phase 5 — Figures (family C): ✅ BUILT (D-279), on the user's decision.**
> Deterministic SVG from a structured spec the gate verifies, not generated images. **28 items
> across 4 topics** — `telling_time`, `data_graphs`, `plane_figures`, `coordinate_geometry` — and
> the contract that makes the remaining C rows authorable. The *decision gate* this phase was
> written around is therefore closed: build, not defer.
>
> *Done when* (from the original phase text): the renderer family ships with per-family tests ✅
> (18), and one C topic passes a Phase-1-style wave — **partially**: four topics are authored and
> gated, but they are authored rather than generated, so "a wave" does not apply in the form the
> criterion assumed. Recorded rather than claimed.

**Phase 3 — Scale + the auto-approval decision.**
Go/no-go per pre-registered criteria: yield ≥ ~50% of scheduled slots, human rejection < ~30%,
dispersion real per rubric, zero leaked-answer/meta-text defects reaching `pending`, cost per
accepted item within cap. If the measured human-rejection rate on clean-pass items is near zero,
implement the deferred **auto-approval slice with random spot-check sampling** (the
QUESTION_GENERATION.md §9 condition, now with evidence) — without it, target depth is not
reviewable by one person; the user decides this explicitly either way. Then deepen every A/B
topic to **5–7 items per occupied tier (~25–35/topic, ~1,000 items across 34 topics)** — the
D-223 measured target, chosen by the user over SPEC §5.8.1's unmeasured 100/topic (~3,400 items,
3× the spend and review burden) — in band batches, each batch its own PR.
*Done when:* every A/B row is a stocked skill at target depth, total spend stayed within the
per-run caps, and the auto-approval decision is recorded in DECISIONS.md with the numbers that
drove it.

⏸ **partial, 2026-08-12 — D-289 through D-292.** Clause by clause:

- **The auto-approval decision is recorded with its numbers: ✅ D-289.** All five pre-registered
  criteria pass — yield 57-91%, human rejection 13% with 0 wrong answer keys, dispersion real in
  26 of 26 generated topics, **0 of 658** bank items failing today's full gate, 4.7¢ per accepted
  item. The user's decision was **auto-approve with no spot-check sampling**; a 20-item-per-wave
  sample was recommended and declined, and D-289 records both.
- **Total spend stayed within the per-run caps: ✅** every run behind a preflight and an explicit
  `--run-budget-cents` sized from its own scheduled-candidate count.
- **Every A/B row stocked at target depth: ❌ not yet**, and the reason is measured rather than
  a shortfall of effort. See D-292.

**What the phase found that its criteria did not ask about.** Three defects, each blocking
content that no amount of spending would have produced:

1. **`g5_word_problems` could never open** (D-290) — its skills spanned `[2,3]`, `[3,4]`, `[4,5]`,
   so the plan could not schedule a tier-1 item while the serving floor demands one. Fixed, with
   a test asserting every authorable topic's plan spans all five tiers.
2. **`algebra_1` tier 1 had never been achievable** (D-291) — `Eq(x**2, 64)` for a square's side
   derives `{8, -8}` and was held against "8 metres". D-281's interval defect in a second answer
   model; **7 of 7** candidates ever generated died on it.
3. **The difficulty judge does not reproduce its own labels** (D-292) — re-judging 16 shipped
   bank items at their own tiers gives **19% exact agreement, 88% within one tier**, drifting
   about a tier downward. 52% of this phase's rejections were difficulty disagreements, and the
   tier-4/5 slots are therefore priced against instrument noise rather than content difficulty.

**Serving floor: 13 topics below it → 8; openable topics 20 → 25 of 33; the bank 658 → 852.**
On the user's decision the depth pass ran at **the tiers each topic's plan already spans**,
accepting retiering rather than paying ~3× to fight it: **25 topics, 156 accepted of 257 (61%),
$9.02**, against 35 of 99 (35%) when the serving-floor batch targeted the extremes directly. The
difference between those two yields is D-292 measured from the spending side.

**What remains, and why it is not a spending problem.** 14 items stand between 8 topics and being
openable, and **12 of them are tier 5**. Depth against D-223's 5-per-tier target is **83 of 165
(topic × tier) cells**, with the unfilled half concentrated at tiers 4-5. Both numbers are gated
on the same question — whether the difficulty rubric or the five-tier requirement is what should
change — which is the first item of the next session rather than more generation.

> **⏸ Amended again 2026-08-13 (D-300 → D-306). The openability half of this phase is DONE;
> the depth half is not, and the reason changed.**
>
> - **Serving floor: ✅ 33 of 33 topics openable.** The "14 items short" figure was an artefact of
>   requiring two items at *every* tier. D-300 found the premise under it was false — a ±1 judge
>   disagreement is `flagged` and keeps the **slot's** tier, so 327 of 759 serving items were
>   labelled by the plan rather than the judge, and the judge agrees with *its own* first rating
>   62%/88% against 19%/69% versus the stored tier. On that evidence the user decided: follow the
>   judge, accept an uneven and biased tier distribution, fill the question count. Both halves had
>   to move together (judge's tier alone: 26 → 12 openable; with `EXAM_QUESTION_COUNT`: 33 → 33).
>   Verified in a browser — local e2e 70/70 including all four band walks — and every formerly
>   closed topic builds a real 10-question exam. **Cost, stated because it is a product change:**
>   `g2_word_problems` now draws 7 of 10 items at tier 1.
> - **Depth against D-223's 5-per-occupied-tier target: ⛔ 82 of 152 cells (54%).** Comparable to
>   the 83 of 165 at the last close — this session added 84 items but re-tiering redistributed the
>   cells. **The remaining blocker is content-shaped, not spend-shaped**, and is now named: the
>   equal-valued-distractor class (64 rejections) concentrated in the canonical-form skills.
>   D-306 tested the repair path against it at two budgets and it does not converge —
>   `g6_fraction_reduce` took 0 of 4 both times, oscillating rather than improving, because the
>   model's conception of "reduce to lowest terms" *is* the ungradeable item. A canonical-form
>   check (`gcd == 1`) is sized at 16 of 44 recoverable and is the open option.
> - **Total spend within per-run caps: ✅** every run behind a green preflight and an explicit
>   `--run-budget-cents`; **$4.50** across seven paid runs this session.

> **⏸ Amended 2026-08-12 by D-295 — the diagnosis above is incomplete, and the correction is
> cheaper than either option it offered.** `judge_difficulty` *retiers* a `slot_gap >= 2` when
> the run's histogram shows the judge discriminating and rejects only when it does not, so the
> **87 retiered and 117 rejected candidates are the same disagreement at the same tiers**. And
> `_MIN_JUDGE_OBSERVATIONS = 5` blocks **100% of positions 1-4 of every run** against 0.6% at
> position 11+, so **the cost driver is the number of runs, not the tier mix** — this depth pass
> ran many small per-topic batches and paid ~4 un-retierable candidates each time. Re-running it
> as one large run is the first thing to try, and it needs no code change; the rubric question
> (D-292) is still open but should be measured against runs that are not also paying a warm-up
> toll. D-292's description of the ±1 policy is also backwards on both halves — see D-295.

**Phase 4 — Video catalog across the taxonomy.**
Runs after Phase 1's taxonomy lands (the classifier can only assign skills that exist). Choose
K-12 math channels; verify YouTube API key + `packages/youtube` settings prerequisites; run
`make youtube-sync` against dev, read the classifications against the expanded taxonomy, then
run against staging. Quota and per-video classify+embed costs budgeted up front. A skill with no
suitable video keeps the §5.11.6 fallback — designed behaviour, recorded as a disposition.
*Done when:* every stocked topic has ≥1 approved video or a recorded no-suitable-video
disposition, staging `youtube_videos` is non-empty, and a staging walk serves a real video from
the intervention menu.

**Phase 5 — Figures (family C): decision gate, then build if approved.** *(Superseded by the
✅ block above — the decision was taken on 2026-08-12 and the answer was build. Original
phase text kept because its "done when" is what the block above is measured against.)*
Proposal on the table (D-273): deterministic parameterized SVG renderers (clock faces, coin
sets, bar charts, labeled shape/angle diagrams) rendered client-side from structured fields the
gate already verified — no image generation, no blob storage, no new PII surface. This is a
feature (data model + renderers + frontend + generation contract), not content; it gets its own
design doc and DECISIONS entry before any code.
*Done when:* the user's build/defer decision is recorded; if build — the renderer family ships
with per-family tests and one C-topic passes a Phase-1-style wave; if defer — every C row's
disposition in the coverage matrix says so.

**Phase 6 — Per-band end-to-end + deploy verification.**
Full walk per grade band on staging: topic resolves → pre-exam → study with hint/solution/
video/tutor → post-exam. Two checks that only matter now: grade-1 reading level in stems *and*
tutor replies, and math rendering for advanced content (exponents, radicals, calculus notation
in the React frontend — untested today because no content needed it). `make lint typecheck
test` + e2e (never concurrently with pytest — shared dev Postgres).
*Done when:* e2e green including new-band walks, zero console errors on the full walks, and
staging serves the seeded bank end to end.

⏸ **partial, 2026-08-12 — D-288.** Measured against the criterion above, clause by clause:

- **New-band walks: ✅** `journey-bands.spec.ts` walks grade 1 × Telling the Time (the figure
  walk — the clock SVG is asserted), grade 4 × Multi-Digit, grade 7 × Pre-Algebra, grade 10 ×
  Calculus. All four pass **on staging**, each on its own fixture student.
- **Zero console errors on those walks: ✅** enforced by the capture fixture over each walk.
- **Staging serves the seeded bank: ✅ and it did not before.** 17 of 33 topics were below the
  per-difficulty serving floor and could not be opened at all; the four figure topics are fixed
  here, and the other 13 are Phase 3's deepening pass with a per-tier shopping list.
- **e2e green as a whole run: ❌** staging is 22 passed / 2 failed. One is a product defect with
  four explanations tested and killed (D-288); the other is `time-telemetry`.
- **Math rendering for advanced content: ✅, and it was broken** — options rendered raw, so 64
  fields showed students SymPy. Fixed, with a gate check.
- **Grade-1 reading level: ⏸ half measured, half still open (D-303, 2026-08-13).** The
  *deterministic* path — 912 items of stems, hint ladders and solution steps, which is what a
  student reads when they ask for help — runs at a **median 7-9 words per sentence in every
  band** (band 1-2: median 7, p90 14, max 21), nowhere near the 30-word ceiling; 26% of band-1-2
  sentences pass a rough 10-word grade-1 guide, which is the honest residual. Measuring it found
  the ceiling was **evadable**: it split on every period *including decimals*, so a 33-word
  sentence carrying six decimals passed while the same sentence spelled out was rejected at 51
  words. Fixed, with 0 of 9,552 bank sentences having exploited it. **Still open:** the
  *generative* path (`generate_hint` / `generate_solution` / `generate_personalized_hint`) has no
  readability check and `tutor_chat_messages` holds 0 rows, so measuring it needs paid generation
  of a fresh sample rather than production behaviour.

**Budget guardrails, session-wide:** every paid run behind a green preflight and an explicit
`--run-budget-cents`; waves sized to ~100–150 review items so the human bottleneck is paced;
generation is the cheap part (pilot ~$15–40, full depth low hundreds of dollars at the one
measured rate) and the caps, not the estimates, are the bound.

### Parallel track (any time, non-coding) — Phase 0 legal & policy docs (§6.1)
Privacy Notice, AI Use Notice, product Learning Notice, retention policy, etc. Drafting can
happen in a writing-focused session; **counsel review is a launch gate, not a dev blocker.**
**Now also gating a coding session (D-129, T-02): enumerate §5.1.2's eleven first-visit
disclosures** — AI may err; AI does not replace a tutor; exam results adjust the estimated level;
limited sharing with tutors/branch managers; parents see the complete record; learning memory is
created from questions and events; images are deleted immediately; YouTube recommendations;
minimized external data; the right to challenge results; the right to report questions — as a
written deliverable **S45 transcribes rather than drafts**. It must agree with the Privacy Notice,
including D-114 §4's standing obligation to state the 90/90/365 retention windows and to avoid
implying that deleting a chat removes text derived from it.
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
