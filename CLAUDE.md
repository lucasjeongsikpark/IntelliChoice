# IntelliChoice — Project Instructions

> Last reviewed: 2026-08-21 (execution-mode adapter added; content baseline: the 2026-08-20
> documentation reconciliation migration). This file has drifted silently before (rule 1 said
> "MongoDB" until D-082/D-111) — if this date is old, distrust the descriptions below and verify
> against `docs/PROJECT_STATE.md`.

AI education platform for K–12 students (minors are the primary users). Two independently
deployed apps sharing auth from the existing `go.intellichoice.org` system:

- **Adaptive Learning** (`learning.intellichoice.org`) — attendance-gated pre-exam →
  personalized study → post-exam → learning gain → parent reports.
- **Organization Q&A** (`chat.intellichoice.org`) — role-aware RAG over org documents,
  branch locator, calendar, admin escalation.

Those product hostnames do not exist live yet: deployed staging is reached through the two
CloudFront domains (`RD-12-INGRESS`), the ALB admits traffic only from CloudFront's prefix list,
and a direct-to-ALB timeout is by design, not an outage.

## Execution modes — who reads what at startup

This file is a thin runtime adapter for three execution modes. The canonical project-memory
model (the documents indexed below) is identical in all three; only startup reading and write
ownership differ. Full role rules: `docs/reference/AUTHORITY_MODEL.md` §6.

- **Standalone Claude Code** — this file is auto-loaded. Read `docs/PROJECT_STATE.md` first,
  then only the task-relevant active/reference material (AUTHORITY_MODEL §6.1).
- **Orca coordinator** — this file is auto-loaded. Read `docs/PROJECT_STATE.md` first. The
  coordinator owns project-context interpretation and the AUTHORITY_MODEL §4 conflict protocols;
  it reads task-relevant SPEC / ARCHITECTURE / DECISIONS / TRACEABILITY / reference material as
  needed, and verifies material current-state assumptions against primary evidence before
  freezing a non-trivial task.
- **Orca executor** — read the coordinator-created Frozen Spec first (contract below). Do NOT
  independently reconstruct project-wide state from `PROJECT_STATE`. Read only the task-scoped
  authoritative references the Frozen Spec names, plus implementation-relevant primary evidence
  (code, tests, config). Never read `docs/archive/` as current context — the archive is never
  handed to an executor (AUTHORITY_MODEL §6.2).

## Documents — the index (complete by rule)

**Read `docs/PROJECT_STATE.md` first** (standalone and coordinator modes; an Orca executor
starts from its Frozen Spec instead — see "Execution modes" above). It is the entry point:
current state, the deploy gap, active work, open user decisions, the freeze, and the map of
everything below. Precedence when documents disagree:
[docs/reference/AUTHORITY_MODEL.md](docs/reference/AUTHORITY_MODEL.md).

**Rule for this index: every non-archive document is listed here, or explicitly listed as
deliberately unlisted with the reason.** An unlisted document is invisible at session start —
that failure mode is what this rule exists to prevent.

The five active documents:

- [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) — THE entry point (above).
- [docs/SPEC.md](docs/SPEC.md) — the complete normative spec (~4,400 lines; its H1 says "5. Very
  Detailed Version" but it is the whole product spec). **Do not read it whole**; read the
  sections your task touches. Amended in place with dated markers — see its "SPEC amendments"
  index at the top.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — **the single as-built authority** and sole owner
  of the storage-split table, deployed topology, scheduler state, and the explicitly-marked open
  architecture questions. The file every session that ships architecture-level change must update.
- [docs/DECISIONS.md](docs/DECISIONS.md) — the append-only judgment/rationale record, the system
  of record for judgements. Navigate by its own decision-ID index; read its "How to read this
  log" section before keying anything on headings. ID sequences contain phantom/missing entries
  (cited but never written), and the highest decision ID implies nothing about current state —
  never infer current state from it.
- [docs/TRACEABILITY.md](docs/TRACEABILITY.md) — the living §2.6 criterion-1 evidence instrument.
  Read its method section before adding rows — "unverified counts as not traced".

Reference (durable, read on demand — not per-session):

- [docs/reference/AUTHORITY_MODEL.md](docs/reference/AUTHORITY_MODEL.md) — which document wins,
  the two precedence ladders, conflict protocols.
- [docs/reference/INCIDENT_RESPONSE.md](docs/reference/INCIDENT_RESPONSE.md) — the incident
  runbook (leaked credential, auth bypass, cost anomaly), grounded in this project's real
  incidents (S32/D-084, S33/D-085, D-310, D-400).
- [docs/reference/QUESTION_GENERATION.md](docs/reference/QUESTION_GENERATION.md) — the as-built
  offline question-generation pipeline. Read before changing `packages/curriculum`'s pipeline.
  D-342 parks all coverage-driven generation runs — a standing user instruction.
- [docs/reference/HINT_SOLUTION_REVIEW.md](docs/reference/HINT_SOLUTION_REVIEW.md) — the
  **as-built** hint/solution review instrument (reconciled 2026-08-20; formerly described here as
  "the planned design"). Read before adding any hint- or solution-quality scoring — two earlier
  scorers failed and §1 explains why.
- [docs/reference/U7_CHECKPOINT_CONSOLIDATION.md](docs/reference/U7_CHECKPOINT_CONSOLIDATION.md) —
  the only staging checkpoint sizing that exists; its questions are answered (D-333). D-333's
  precondition binds any retention change: consolidate memory before deleting any checkpoint.
- [docs/reference/CONTENT_COVERAGE.md](docs/reference/CONTENT_COVERAGE.md) — taxonomy
  denominators (as-of 2026-08-11; status columns are dated, trust the annotations).
- [docs/reference/FIRST_VISIT_NOTICE.md](docs/reference/FIRST_VISIT_NOTICE.md) — the only written
  copy of all eleven disclosures; input to the frozen consent session S45 (UD-10 open).
- [docs/reference/integration/](docs/reference/integration/) — **the D-152-frozen world**, banner
  gated: `INTEGRATION_PLAN.md` (the plan the freeze binds), `S42_DISCOVERY.md` (production facts
  read from source), `S42_OPEN_QUESTIONS.md` (the org-facing register, Korean),
  `ROADMAP_FROZEN_SESSIONS.md` (S42–S51 scope). Nothing in there is startable work.
- [docs/reference/org-drafts/](docs/reference/org-drafts/) — the two live outbound drafts:
  `S42_SECURITY_REPORT.md` (send permitted under the freeze, INT-28; no send recorded as of
  2026-08-20) and `ENROLLMENT_FAQ_APPROVAL.md` (the sole launch gate on the guest journey's
  canonical question — awaiting the org's approval). Whether committed drafts are allowed at all
  is UD-12(f), open.
- [docs/reference/audits/](docs/reference/audits/) — the three audit registers behind
  `README.md`'s namespace map. **Never cite a bare audit ID** — always `<document>:<id>`; four ID
  schemes collide across the three files.
- [docs/reference/reconciliation-2026-08/](docs/reference/reconciliation-2026-08/) — the
  166-entry `FINAL_OPEN_WORK_REGISTER.md` and `USER_DECISION_QUEUE.md`: the provenance backbone
  `PROJECT_STATE` links into. Evidence, not authority.

Deliberately unlisted:

- `docs/archive/` — historical only, indexed by [docs/archive/README.md](docs/archive/README.md);
  every file carries an ARCHIVED banner. Unlisted here because nothing in it is current, and
  listing archives beside live documents is the misleading-active pattern this index was rebuilt
  to end. (`ROADMAP.md`, `PROGRESS.md`, `OPEN_DECISIONS.md` live there now — all their open items
  were carried into `PROJECT_STATE` or the register before archival.)
- `docs/log/` — append-only per-session narration, **non-authoritative** (user ruling DQ-1).
  Agents do not read the full log by default; rules in `docs/log/README.md`.
- `tasks/` — **deliberately outside this index.** Frozen Specs are temporary task-scoped working
  contracts (see "Orca coordinator / executor workflow"), not canonical project documentation,
  and never a source of current project truth after their task closes.

## The existing production system

Its source is checked out at `../IntelliChoice-web` (`icrest/` Express+Sequelize backend,
`icweb/` React frontend) and is **the source of truth for the existing system** — read it rather
than guessing or waiting on the org. Two hard rules: **never read `icrest/app/config/db.config.js`
or `intellichoice-sendmail-*.json`** (committed credentials), and never quote the source-visible
JWT secret or password-HMAC key values anywhere. Production is **frozen** — findings about it get
reported to the user, never fixed here. (`docs/codebase-analysis/` references resolve to
`../IntelliChoice-web/docs/codebase-analysis/` — out of this repository.)

### ⛔ Integration is deliberately deferred (D-152) — do not "unblock" it

The user's sequencing decision: **finish and test this codebase against the dev fakes first, then
integrate.** Reconfirmed 2026-08-18 (D-417 §A1): *"D-152 is unchanged and is not 'nearly met' — it
is closed until reopened."* The two documents the freeze binds:
[docs/reference/integration/INTEGRATION_PLAN.md](docs/reference/integration/INTEGRATION_PLAN.md)
and [docs/reference/integration/S42_DISCOVERY.md](docs/reference/integration/S42_DISCOVERY.md) —
both carry line-1 freeze banners. So in any session, unless the user explicitly says integration
is starting:

- **Do not** measure AWS→icrest reachability, request the production API URL or a test account, or
  finalize the §3.1 auth option. O1b stays a *recommendation* until measured, right before S44.
- **Do not** treat S43–S51 items or the S42 open-questions groups as blockers. They are frozen by
  choice, not stuck. No measurement or green suite can meet the reopen condition — it is a user
  decision, and soliciting one is forbidden.
- **Do not** rewrite the MySQL dev fake to match production's schema. Its shape is wrong on
  purpose: the `ProfileAdapter` Protocol is SPEC-derived, not fake-derived.
- **Do** keep the seam honest. Anything that would make an app-level decision depend on the fake's
  *schema* rather than on the Protocol is a real defect — say so.

The one production fact that must inform product work **now**: `signups.attended = null` ("manager
hasn't marked it yet") is common, so `AttendanceStatus.UNKNOWN` → blocked is a **routine** path in
production, not a rare one (D-152 §2).

## Session workflow (role-aware)

Current and open state lives in `docs/PROJECT_STATE.md` (delete-on-resolve) in every mode. All
modes stay within the chosen item's / Frozen Spec's scope; new discoveries become new
`PROJECT_STATE` rows (written by the role that owns them), not detours.

- **Standalone Claude Code** — start every working session with `/start-session [item]` and end
  with `/end-session`; update current/open state per `PROJECT_STATE`'s update protocol and
  AUTHORITY_MODEL. Per-session narration goes to git commit messages and `docs/log/`.
- **Orca coordinator** — owns the task/session lifecycle; owns canonical documentation
  reconciliation after accepted work; owns `PROJECT_STATE` updates (the only Orca role that
  edits it); session narration goes to `docs/log/` under its authority rules
  (`docs/log/README.md` — append-only, non-authoritative).
- **Orca executor** — does NOT run `/start-session` or `/end-session`; does NOT independently
  update `PROJECT_STATE`; does NOT independently amend SPEC, ARCHITECTURE, DECISIONS, or
  TRACEABILITY. It reports documentation impact and conflicts to the coordinator.

## Orca coordinator / executor workflow

A workflow adapter only. Project memory stays in the documents indexed above — nothing in this
section restates project state, and it must never grow a second copy of it.

**Coordinator responsibilities:** understand the user goal (a generic continue/resume request
means: the first eligible item of `docs/PROJECT_STATE.md` §4.4's execution queue — see "Task
selection" below); investigate project context; make
implementation/technical-design choices only where existing project authority (SPEC as amended,
accepted decisions, ARCHITECTURE) legitimately determines them; create the Frozen Spec; delegate
non-trivial implementation through Orca; answer executor technical questions; independently
review the actual diff and verification evidence; accept or reject the implementation; reconcile
canonical docs only after acceptance. The coordinator must NOT independently create or resolve a
new product, business, policy, safety, or USER decision — if existing authority cannot determine
such a question, escalate to the user (AUTHORITY_MODEL §4.6).

**Executor responsibilities:** implementation; tests; debugging; lint/typecheck/build and other
relevant verification; self-review; concrete evidence. An executor must not reinterpret
project-level decisions, answer USER decisions, reconcile canonical documentation, or silently
choose between conflicting documentation and primary evidence — a conflict is returned to the
coordinator as a finding (AUTHORITY_MODEL §6.2).

### Role selection and handoff

- Execution mode is **explicit, never inferred** from the filesystem or worktree path.
- A top-level user-facing Claude session asked to run an Orca coordinator/executor workflow acts
  as the Orca coordinator.
- When the coordinator dispatches implementation, the worker prompt must explicitly identify
  that worker as the Orca executor and name the Frozen Spec path it must follow.
- An executor must not infer its role merely from being inside an Orca-created worktree.
- If an Orca role is genuinely ambiguous, do not mutate project state until the role is
  established.

### Task selection — the PROJECT_STATE execution queue

- On a generic continue/resume request ("continue the project", "do the next task"), the
  coordinator takes the **first eligible item** of `docs/PROJECT_STATE.md` §4.4 (the execution
  queue — canonical execution state, single-homed there). It verifies §4.4's eligibility gate
  against the register row and primary evidence *before* writing the Frozen Spec, and does not
  independently reprioritize the queue during an ordinary continue.
- If the first item fails the gate (stale, no longer eligible), it is **not silently skipped**:
  reconcile PROJECT_STATE per AUTHORITY_MODEL's conflict rules first, then take the newly valid
  first item.
- A **user-named task overrides the queue** only when it is legitimately startable and the
  request does not conflict with existing decisions or freeze boundaries (D-152, PROJECT_STATE
  §6, unresolved UDs); a conflicting request is surfaced to the user, not worked around.
- **Executors never select, reorder, or advance project tasks**; they start from the Frozen Spec
  they are handed. Only the coordinator (or a standalone session) advances or reconciles the
  queue, and a completed task advances it only **after** coordinator acceptance and
  canonical-document reconciliation.
- One task per generic continue request: after advancing the cursor, stop — unless the user
  explicitly asked for multiple tasks.

### Orca orchestration mechanics

Before creating or mutating Orca orchestration state, the coordinator must:

1. load the installed, version-matched orchestration instructions:
   `orca skills get orchestration --full`;
2. confirm Orca is reachable: `orca status --json`;
3. use the lifecycle and commands from the installed skill, never memorized Orca CLI syntax.

For the current sequential workflow: exactly **one implementation executor per task**; target
**Claude Opus 5 with high effort** when that model is available in the installed Orca runtime;
verify the effective executor/model from Orca's launch receipt when available, and never
silently substitute another executor model if the requested one was not actually selected;
preserve the **same persistent executor** across ordinary correction rounds whenever Orca
supports it; do not launch a separate evaluator by default — the coordinator remains the
independent final reviewer.

The normal flow: user goal → coordinator context investigation → Frozen Spec → Orca persistent
executor → executor implementation/self-verification → coordinator independent review →
same-executor correction loop if needed → coordinator acceptance → coordinator-owned
canonical-doc reconciliation. The user is never required to manually create Orca tasks, launch
the executor, relay messages between coordinator and executor, or mediate routine correction
rounds.

### Frozen Spec contract

For every non-trivial Orca task the coordinator creates `tasks/<descriptive-task-name>.md` with
these sections: Objective; Authoritative References; Current Relevant State; Intended Behavior;
Repository Evidence; Deployed-State Relevance; Decision Boundaries; Known Drift / Uncertainty;
Current Context; Required Behavior; Scope; Non-Goals; Constraints; Acceptance Criteria;
Verification. The Frozen Spec must give the executor enough task-scoped context that it never
needs to reconstruct project-wide truth independently. Files under `tasks/` are task-scoped
working artifacts, not project documentation — they sit outside the docs index above and are
never a source of current project truth after their task closes. After coordinator acceptance
and canonical-document reconciliation, delete the completed Frozen Spec unless it is still
needed for an active correction or an explicitly retained follow-up; durable outcomes belong
in canonical docs, `docs/log/`, and git history.

### Executor completion evidence

The executor reports: Files Changed; Verification Performed; Verification Results; Observed
Drift; Documentation Impact; New Decision Required; Remaining Uncertainty. When no new decision
is needed, write `New Decision Required: none` explicitly.

### Coordinator acceptance

After executor completion, the coordinator independently compares the Frozen Spec vs. the actual
diff vs. the verification evidence. If implementation corrections are needed, send them back to
the same persistent executor where the Orca runtime supports that. Only after accepting the
implementation may the coordinator reconcile canonical project docs. A `PROJECT_STATE` item is
deleted only when its actual completion condition is satisfied; partial progress restates the
row rather than falsely resolving it. Session chronology never goes in `PROJECT_STATE`.

## Stack

Python 3.12, FastAPI (async), LangGraph, LlamaIndex, SQLAlchemy + Alembic,
Pydantic v2 everywhere, PostgreSQL 16 + pgvector, MySQL 8.4 (read-only adapter; D-082/D-083),
AWS Bedrock behind a gateway, pytest. Frontends: React + Vite. Local dev: Docker Compose.

## Non-negotiable rules (condensed from SPEC.md — the spec carries the detail; when documents conflict, use AUTHORITY_MODEL §3, not this list)

1. **No student, parent or guardian PII in Postgres — absolute.** Two tables (org staff/branch
   contact) carry the org's own already-public fields under an enumerated exemption (D-050,
   `ALLOWED_PII_SHAPED_COLUMNS`); `test_schema_purity.py` still fails loudly if any student-facing
   table grows one of those column names. Postgres otherwise stores only `*_external_id`
   references; the org's MySQL database remains the source of truth for names, emails, roles,
   relationships, attendance (SPEC §5.4, §5.30). No PII in logs, traces, or LLM payloads — no
   exemption there.
2. **Deterministic core.** Grading, attendance gating, authorization, score/gain calculation,
   and SQL execution are never done by an LLM (SPEC §5.0, §5.26). No runtime NL2SQL.
3. **Authorization in the backend/query layer, never in prompts.** Parent-child links are
   verified server-side; role/branch filters are applied *before* RAG retrieval (SPEC §5.21.3,
   §5.30.2).
4. **Every external action needs human approval** via LangGraph `interrupt()`: emails,
   calendar events, location use, image analysis (SPEC §5.1.4, as amended 2026-08-20).
5. **Fail closed.** Unknown attendance ≠ present; no RAG answer without an approved,
   effective, citation-supported source (SPEC §5.4.4, §5.21.8, §5.29).
6. **Structured LLM output only:** JSON-schema output → Pydantic validation → limited repair
   retry → deterministic fallback. Invalid tool calls never execute (SPEC §5.25.3, §5.27).
7. **All model/paid-API calls go through the gateway** with timeouts, bounded retries,
   max-token limits, and cost accounting (SPEC §5.25.1).
8. **Solution images are deleted immediately** after analysis, success or failure, and never
   enter backups, traces, or logs (SPEC §5.17). Requirement unchanged; no code path implements
   §5.17 today — the requirement binds any future implementation from line one
   (`IMAGE-WORK-PARK`).
9. **External deps behind interfaces with dev fakes** (auth, MySQL, Bedrock, Gmail/Maps/
   Calendar, blob storage). Real clients are env-selected (DECISIONS.md D-002).
10. Student-facing language is growth-oriented and age-appropriate; internal skill IDs stay
    internal (SPEC §5.10.3).

## Conventions

- Thin route handlers; separate config / provider clients / services / routes.
- Explicit Pydantic models at every boundary (API, graph state, tool args, LLM output).
- Alembic migration for every schema change; migrations must replay from empty.
- Tests accompany the work item's verification plan; run `make lint typecheck test`
  before declaring work done.
- Never read or write `.env` or any credentials; use `.env.example` for shape.
- Any number about the deployed system carries its build SHA and as-of date (LB-05);
  "implemented locally" is never reported as "deployed".
