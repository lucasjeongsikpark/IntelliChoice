# IntelliChoice — Project Instructions

AI education platform for K–12 students (minors are the primary users). Two independently
deployed apps sharing auth from the existing `go.intellichoice.org` system:

- **Adaptive Learning** (`learning.intellichoice.org`) — attendance-gated pre-exam →
  personalized study → post-exam → learning gain → parent reports.
- **Organization Q&A** (`chat.intellichoice.org`) — role-aware RAG over org documents,
  branch locator, calendar, admin escalation.

## Documents — read these instead of holding the spec in your head

- [docs/SPEC.md](docs/SPEC.md) — the complete detailed spec (~2,600 lines). **Do not read it
  whole**; read only the sections the current session lists in ROADMAP.md.
- [docs/ROADMAP.md](docs/ROADMAP.md) — session-by-session implementation plan and "done"
  criteria. The source of truth for what to build next.
- [docs/PROGRESS.md](docs/PROGRESS.md) — current status, session log, carry-over items.
- [docs/DECISIONS.md](docs/DECISIONS.md) — decision log; check before re-deciding anything.
- [docs/TRACEABILITY.md](docs/TRACEABILITY.md) — the §2.6 criterion-1 evidence: which launch-scope
  SPEC requirements are traced to implementation *and* test, which are dispositioned, which are
  gaps. Read its method section before adding rows — "unverified" counts as not traced.
- [docs/INCIDENT_RESPONSE.md](docs/INCIDENT_RESPONSE.md) — the practical runbook for a real
  incident (leaked credential, auth bypass, cost anomaly, etc.), grounded in this project's own
  real incidents (S32/D-084, S33/D-085).
- [docs/S42_DISCOVERY.md](docs/S42_DISCOVERY.md) — what the **existing** `go.intellichoice.org`
  system actually does, read from its own source (D-151). Read this before assuming anything about
  production's schema, roles, attendance, or login contract.

## The existing production system

Its source is checked out at `../IntelliChoice-web` (`icrest/` Express+Sequelize backend,
`icweb/` React frontend) and is **the source of truth for the existing system** — read it rather
than guessing or waiting on the org. Two hard rules: **never read `icrest/app/config/db.config.js`
or `intellichoice-sendmail-*.json`** (committed credentials), and never quote the source-visible
JWT secret or password-HMAC key values anywhere. Production is **frozen** — findings about it get
reported to the user, never fixed here.

### ⛔ Integration is deliberately deferred (D-152) — do not "unblock" it

The user's sequencing decision: **finish and test this codebase against the dev fakes first, then
integrate.** So in any session, unless the user explicitly says integration is starting:

- **Do not** measure AWS→icrest reachability, request the production API URL or a test account, or
  finalize the §3.1 auth option. Those results go stale before they are used; O1b stays a
  *recommendation* until measured, right before S44.
- **Do not** treat S44+ items or [S42_OPEN_QUESTIONS.md](docs/S42_OPEN_QUESTIONS.md) groups A/B/C/D
  as blockers. They are frozen by choice, not stuck.
- **Do not** rewrite the MySQL dev fake to match production's schema. Its shape is wrong on purpose
  and that is safe: the `ProfileAdapter` Protocol (`StudentProfile`/`BranchInfo`/`AttendanceStatus`)
  is SPEC-derived, not fake-derived, so the mismatches stay behind the adapter seam until S43.
- **Do** keep the seam honest. Anything that would make an app-level decision depend on the fake's
  *schema* rather than on the Protocol is a real defect — say so.

The one production fact that must inform product work **now**: `signups.attended = null` ("manager
hasn't marked it yet") is common, so `AttendanceStatus.UNKNOWN` → blocked is a **routine** path in
production, not a rare one (D-152 §2).

## Session workflow

Start every working session with `/start-session [S<n>]` and end with `/end-session`.
Stay within the active session's roadmap scope; new discoveries become carry-over items,
not detours.

## Stack

Python 3.12, FastAPI (async), LangGraph, LlamaIndex, SQLAlchemy + Alembic,
Pydantic v2 everywhere, PostgreSQL 16 + pgvector, MySQL 8.4 (read-only adapter; D-082/D-083),
AWS Bedrock behind a gateway, pytest. Frontends: React + Vite. Local dev: Docker Compose.

## Non-negotiable rules (condensed from SPEC.md — the spec wins on detail)

1. **No PII in Postgres, logs, traces, or LLM payloads.** Postgres stores only
   `*_external_id` references; the org's MySQL database remains the source of truth for
   names, emails, roles, relationships, attendance (SPEC §5.4, §5.30).
2. **Deterministic core.** Grading, attendance gating, authorization, score/gain calculation,
   and SQL execution are never done by an LLM (SPEC §5.0, §5.26). No runtime NL2SQL.
3. **Authorization in the backend/query layer, never in prompts.** Parent-child links are
   verified server-side; role/branch filters are applied *before* RAG retrieval (SPEC §5.21.3,
   §5.30.2).
4. **Every external action needs human approval** via LangGraph `interrupt()`: emails,
   calendar events, location use, image analysis (SPEC §5.1.4).
5. **Fail closed.** Unknown attendance ≠ present; no RAG answer without an approved,
   effective, citation-supported source (SPEC §5.4.4, §5.21.8, §5.29).
6. **Structured LLM output only:** JSON-schema output → Pydantic validation → limited repair
   retry → deterministic fallback. Invalid tool calls never execute (SPEC §5.25.3, §5.27).
7. **All model/paid-API calls go through the gateway** with timeouts, bounded retries,
   max-token limits, and cost accounting (SPEC §5.25.1).
8. **Solution images are deleted immediately** after analysis, success or failure, and never
   enter backups, traces, or logs (SPEC §5.17).
9. **External deps behind interfaces with dev fakes** (auth, MySQL, Bedrock, Gmail/Maps/
   Calendar, blob storage). Real clients are env-selected (DECISIONS.md D-002).
10. Student-facing language is growth-oriented and age-appropriate; internal skill IDs stay
    internal (SPEC §5.10.3).

## Conventions

- Thin route handlers; separate config / provider clients / services / routes.
- Explicit Pydantic models at every boundary (API, graph state, tool args, LLM output).
- Alembic migration for every schema change; migrations must replay from empty.
- Tests accompany the session's "Done when" criteria; run `make lint typecheck test`
  before declaring work done.
- Never read or write `.env` or any credentials; use `.env.example` for shape.
- Do not commit, push, or deploy unless explicitly asked.
