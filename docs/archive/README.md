# docs/archive/ — the historical record

Nothing in this directory is normative or current. Every file carries an ARCHIVED banner naming
its as-of date, the reason, and its successor. Current state: [../PROJECT_STATE.md](../PROJECT_STATE.md).
Precedence: an archived document is never authority for current state — provenance and forensics
only ([../reference/AUTHORITY_MODEL.md](../reference/AUTHORITY_MODEL.md) §2.7, §3.2).

Archived 2026-08-20 by the documentation reconciliation migration (manifest: this directory's
`reconciliation-2026-08/MIGRATION_MANIFEST.md`, executed and archived the same day; its §5 holds
the ten recorded proof-point outcomes).

| File | What it is | Why archived | Superseded by | As-of |
|---|---|---|---|---|
| `ROADMAP.md` | The session-by-session implementation plan, S0–S51, with gate ledger and track logs | Sessions executed or frozen; live S42–S51 scope extracted | `PROJECT_STATE.md` (state); `reference/integration/ROADMAP_FROZEN_SESSIONS.md` (frozen scope) | 2026-08-20 |
| `PROGRESS.md` | The full session log back to S0 — the corpus's memory | Every live item captured by the Phase-4 register; narration moved to `docs/log/` (DQ-1) | `PROJECT_STATE.md`; `docs/log/` | 2026-08-20 |
| `OPEN_DECISIONS.md` | The option space and deliberation record for 14 decisions | All 14 answered or parked; "a status line is a measurement with an expiry date" | `PROJECT_STATE.md` §5/§9; `DECISIONS.md` outcomes | 2026-08-18 |
| `2026-07-21-final-architecture-projection.md` | A 2026-07-21 architecture projection (formerly `FINAL_ARCHITECTURE.md`) | Self-declared projection; status claims almost all false; both live extractions complete | `ARCHITECTURE.md` | 2026-07-21 |
| `2026-07-24-org-asks-drafts.md` *(untracked, gitignored — deliberate; UD-12(f) open)* | Four bilingual org-ask drafts (formerly `S42_ORG_ASKS.md`) | Asks answered/demoted/withdrawn per D-153; "Send now" markers stale; message text preserved verbatim | D-153 dispositions; `reference/integration/S42_OPEN_QUESTIONS.md` | 2026-07-31 |
| `plans/2026-07-18-expansion-plan.md` | The S17–S28 expansion design (executed 2026-07-19/20) | Executed plan; kept intact for design rationale; predates the D-082/D-111 Mongo→MySQL correction | `ARCHITECTURE.md`; `DECISIONS.md` D-049 + S17–S28 entries | 2026-07-18 |
| `plans/2026-07-19-branding-plan.md` | The branding audit and plan (executed as Session 22.5) | Executed; brand table + BD3 rule promoted to `ARCHITECTURE.md`; its D-number instruction mints duplicates | `ARCHITECTURE.md` brand section; D-065–D-069 | 2026-07-19 |
| `reconciliation-2026-08/` (13 evidence artifacts + 4 migration instruments) | The 2026-08-19/20 reconciliation audit's raw evidence (claim ledger, drift registers, inventories, live/local findings and evidence, supersession map, risk register, the D-310 remediation record) plus the executed migration's instruments: `MIGRATION_MANIFEST.md` (with the ten proof-point outcomes in its §5), `DOCUMENT_MODEL.md`, `ADVERSARIAL_REVIEW.md`, `REVIEW_RESOLUTION.md` | Point-in-time evidence; everything actionable merged into the 166-entry register; the migration completed | `../reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md` | 2026-08-20 |

Notes:

- `reconciliation-2026-08/REMEDIATION_D310_ROTATION.md` is the record that D-310 is **resolved
  historical remediation, never an active exposure** (apply completed 2026-08-20T03:20:57Z; the
  `ps`-visibility residual is unmeasured, not cleared — tracked at `PROJECT_STATE` §4.1
  `D310-RESIDUALS`).
- The two live registers (`FINAL_OPEN_WORK_REGISTER.md`, `USER_DECISION_QUEUE.md`) are **not**
  here — they are reference (`../reference/reconciliation-2026-08/`), because `PROJECT_STATE`
  links into them for per-item evidence.
- Freeze rule: files here are edited never. A defect found in an archived file is recorded in the
  superseding current document, not backported (AUTHORITY_MODEL §4.5).
- Known limitation, accepted: **relative links inside archived files may be broken** — the
  2026-08-20 migration moved their targets, and archived text is not rewritten to chase paths
  (e.g. `ROADMAP.md` carries seven such links). Resolve targets via this README's table or
  `docs/PROJECT_STATE.md` §11. The two deliberate exceptions (edited at migration): ROADMAP's two
  `plans/` pointers, repathed per manifest step 9a.
