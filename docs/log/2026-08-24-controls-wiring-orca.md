# 2026-08-24 — tenth Orca run: the three uninvoked controls wired (D-439)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-439.

## Workflow

Coordinator → Frozen Spec (`tasks/batch-low-unscheduled-controls.md`) → one persistent executor
(claude/opus/high, receipt requested = effective; dispatch `ctx_d61b7c359eba`) → **three
escalations answered mid-run** (two allowlist excuses; the path-aware mechanism convergence) →
worker_done → coordinator review → one naming-correction round (same terminal,
`ctx_12170ed2466f`) → acceptance → landed `b9a6011` (PR #399) → **targeted IAM apply** →
**watched first `workflow_dispatch` run: green** (run 32783980237) → this reconciliation.
Workers released; `tasks/` artifacts deleted after this entry.

## Highlights

- The weekly control was proven against its own real window before it ever ran in CI — and
  that window defeated the scanner three times (timestamps, the collector's bind address, the
  access log's latency), each class escalated rather than patched silently. The third forced
  the real fix: the log allowlist's excerpt-only shape could not tell a `duration_ms` value
  from a leaked latitude on the JSON-walked path; it now shares the trace scanner's
  `(pattern, path)` semantics.
- The executor corrected its own wrong claim (sampling vs enumeration) and invalidated one of
  its own negative controls, converting both into recorded evidence.
- First CI run: positive control 31/31, 133 allowlisted as infrastructure, CLEAN over the
  trailing 8 days; image verdict OK on `gha-898e2fb4270b`. The dead "someone chooses to run
  it" state of criterion 9's log half is over.

## Verification

Executor: suite 1806/2/1 (+22), ruff/pyright clean, terraform validate, five mutation runs,
six live smokes (exit codes recorded). Coordinator: full diff read; 33 focused tests, lint,
typecheck re-run; targeted plan `0/1/0` → apply → "No changes"; the first dispatched run
watched to completion.

## State changes

- `BATCH-LOW-UNSCHEDULED-CONTROLS` deleted from §4.1 and the queue
  (`COST-10-INPUT-BOUND` is now row 1); §8's no-drift-detector method rule narrowed (the
  image-agreement class is now watched; F-03's general rule and the tfvars hazard stand);
  header at `b9a6011` (gap 19); the IAM apply joins the control-plane applies note;
  ARCHITECTURE's scheduled-jobs bullet carries the new enforcement points; TRACEABILITY's
  criterion-9 log half upgraded to a weekly instrument; D-438's trigger fired for the first
  time (skip-notes on both descriptive rows).

## Handoff

- Next queue item: `COST-10-INPUT-BOUND` (read whether settlement uses actual input tokens,
  then the gateway input ceiling) — product code, executor task.
- Standing user items unchanged: UD-13, UD-5's EMF promotion, D310 (a) re-paste.
