# 2026-08-24 — eleventh Orca run: the gateway input ceiling (D-440)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-440.

## Workflow

Coordinator investigation answered the register's mandated pre-question before the spec was
written (settlement is actual-cost end to end → exposure was admission-window only) → Frozen
Spec (`tasks/cost10-input-bound.md`) → one persistent executor (claude/opus/high, receipt
requested = effective; dispatch `ctx_df1bfbd4b246`) → one escalation (the 32k ceiling vs the
unbounded `existing_facts` axis, plus the broken AREAS citation — both ruled) → worker_done →
review → acceptance. Worker settled (runtime retained its terminal); task artifacts deleted
after this entry.

## Highlights

- The AUD-F-34 seam is closed at the gateway: `_HARD_MAX_INPUT_TOKENS = 32_000`, typed
  `InputBudgetExceededError`, refuse-never-truncate, admission pricing the real payload
  through one shared estimator; the embeddings path — which turned out to have **no** bound —
  gained a per-text 8,000 ceiling and lost its under-counting `len//4` estimate.
- The executor measured before asking (every bounded axis clears 32k; `existing_facts`
  crosses at ~100–120 facts) and **corrected the coordinator's own visibility claim**: the
  refusal is caught by consolidation's except arm, so the visible path is the CLI's non-zero
  exit → ops-task-failed rule, not the background-failures alarm. Recorded verbatim in D-440.
- The register's AREAS citation chased an archived phrase; the real live text
  (`AUDIT_FINDINGS.md:1304-1310`, "bounded overshoots… rather than absent ceilings") is
  annotated in place — wrong when written, for the input side.

## Verification

Executor: suite 1814/2/1 (+8, all new, none modified), the discriminating admission test
mutation-checked, ruff/pyright clean. Coordinator: full diff read; 220 adapter/shared tests +
lint + typecheck green; only the named constant and one unrelated comment still say 2000.
Nothing deployed — staging has no input ceiling until the next deploy (LB-05).

## State changes

- `COST-10-INPUT-BOUND` deleted from §4.2 and the queue (`WORK-01-SCOPE-GUARD` is now
  row 1); the `existing_facts` crossover filed on `WORK-35-LEDGER`'s design review;
  ARCHITECTURE's input-bound bullet updated (the seam is bounded since D-440); D-438's
  trigger fired again — skip-notes appended on both descriptive rows.

## Handoff

- Next: `WORK-01-SCOPE-GUARD` (build D-423 steps 1–3; includes telling the user the corrected
  embedding estimate — an acknowledgement, not a decision).
- Standing user items: UD-13, UD-5's EMF promotion, D310 (a).
