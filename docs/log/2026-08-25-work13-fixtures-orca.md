# 2026-08-25 — thirteenth Orca run: fixture isolation landed; a gate finding re-homed WORK-35 (D-442, D-443)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgments:
> D-442, D-443.

## The gate finding first (D-442)

`WORK-35-LEDGER` reached the queue front and failed the eligibility gate: its "free staging
measurement" is free in dollars but the register's own evidence line requires a database
session, which `DB-CONTENT-VERIFY` homes on **UD-2's read-only-session rider**. Reconciled per
§4.4's protocol (row restated as blocked on UD-2, removed from the queue; UD-2's "Blocks?"
turned Yes) — a side-door read via an ad-hoc ECS run-task was considered and rejected by name
as a workaround of a user boundary.

## The task (D-443)

`WORK-13-FIXTURES`, the post-gate queue front. Executor (claude/opus/high, liveness-probed):
21 spec files enumerated with verdicts — 13 session-creators now own seeded students
(`student-ext-14..26`, deliberately unlinked), 7 justified shares, and
`dashboard-chart-labels.spec.ts` exposed as **vacuously passing** on other specs' leftovers,
now honest with its own history (`student-ext-27`), assertions unchanged. DevLoginScreen
mirrors the additions. Landed `80791f3` (PR #405).

## Verification

Three consecutive green full local e2e runs on the final tree (two executor, one
**coordinator-independent** — the browser lane is the one lane CI cannot check), against a
proven-green pre-edit baseline; pytest suite at the exact 1867/2/1 baseline (delta 0);
e2e-typecheck + learning-web tsc/oxlint clean; PII scanner positive controls 31/31 → 45/45,
zero new allowlist entries. `make e2e` never ran concurrently with `make test`.

## State changes

- `WORK-35-LEDGER`: §4.2 row restated (blocked on UD-2, both review inputs carried), queue
  row removed; UD-2's Blocks cell → Yes.
- `WORK-13-FIXTURES`: row and queue entry deleted. **The queue is down to one unblocked
  item**: `M3-D370-SOLUTION-RUNG` (whose staging e2e is itself a paid measurement — verify
  the UD-2 spend posture at dispatch).
- Header at `80791f3` (gap 22).

## Handoff

- **UD-2 now sits at the front of almost everything remaining**: the WORK-35 sizing read +
  design review, the whole-directory staging e2e re-run (its prerequisite landed today), and
  M3-D370's paid staging spec. One user decision unblocks three items.
- Other standing user items: UD-13 (LangSmith quota), UD-5's EMF promotion, D310 (a).
