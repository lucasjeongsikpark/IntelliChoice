# 2026-08-22 — COST-06-FLUSH resolved (fourth Orca coordinator/executor run)

Historical narration only — non-authoritative (DQ-1). Current state: `docs/PROJECT_STATE.md`;
durable evidence: the two new tests in `packages/curriculum/tests/test_authored_pipeline.py`,
`DuplicateTemplateIdError` in `ai_pipeline.py`, the cost-aware duplicate branch in
`pipeline_cli.py`, and git history. No new judgment was made, so no DECISIONS entry exists for
this session.

**Queue-gate note.** This continue arrived at 15:26 UTC — before the day's first post-fix nightly
firing — so queue row 1 (`RD-01` confirmation, time-blocked) failed eligibility exactly as its own
note anticipates, and the cursor took the first work-startable row, `COST-06-FLUSH`. RD-01's
confirmation stays row 1.

**What was done.** Fourth Orca coordinator/executor run. The coordinator verified the gate
(register entry vs. primary evidence at `07a65e2`), identified up front that the register's
"reorder `spend +=` before the `continue`" fix shape is unimplementable as written (`outcome` is
never assigned in the flush-time `except` branch — the paid cost is trapped in
`generate_authored_candidate`'s locals when the exception escapes), froze the task as
`tasks/cost-06-flush-spend-accounting.md`, and dispatched it through Orca
(run `run_3eca896d0add`, task `task_744e95599304`, dispatch `ctx_3621ff6400d1`) to a persistent
executor launched as agent `claude`, model `opus`, effort `high` — requested and effective
identical. Zero correction rounds. No paid calls, no generation run (D-342's park untouched).

**What the executor delivered.** Test-first: the forcing test recorded the pre-fix loss (the
colliding candidate's 0.051 test-cents absent from `summary.total_cost_cents`), and the
budget-overrun test measured the consequence — the pre-fix gate admitted, paid for and persisted
a slot past an exhausted budget (`pending == 1`). Fix: `DuplicateTemplateIdError`, an
`IntegrityError` subclass carrying `cost_cents`, raised at the flushing `create_template`; the
slot-level design/repair spend added on re-raise in `generate_authored_candidate`; `run_plan`'s
branch mirrors `_settle`'s commit-time accounting (run `spend`, `total_cost_cents`,
`skipped_duplicate_id`, rejection). Every existing `except IntegrityError` behaves unchanged;
`_settle` and its two tests untouched. Three vacuity controls (summary line, spend line, the
slot-level carry) each failed exactly the predicted test and were reverted.

**Evidence.** Executor: focused 4 passed, curriculum package 531 passed,
`make lint`/`typecheck`/`test` exit 0 (1762 passed / 2 skipped / 1 xfailed). Coordinator
independently re-ran the duplicate tests (4/4), a forced `duplicate_cost = 0.0` mutation kill
(2 failed as predicted, reverted, tree clean), lint, typecheck, and the curriculum package
before accepting.

**Landing.** Worktree commit `d982f32` cherry-picked to `land/cost06-flush-spend` (tree verified
identical), landed by PR #366 into protected `main` as `ba660e1` after all 12 CI checks passed.

**Reconciliation applied after acceptance.** PROJECT_STATE: §4.1 row and §4.3 paragraph deleted
(counts 24→23, 14→13; §4.3 now "three items"), the `NO-NEW-TEST-CODE` sentence rewritten as a
closed category (all three code-reading-only defects now have executed tests), §4.4 row deleted
and renumbered (19 rows; RD-01's confirmation stays row 1), snapshot header advanced to `ba660e1`
(gap 16). Register: loud dated resolution annotation on `COST-06-FLUSH` including the
unimplementable-wording correction and the retired ledger `CONFLICT` (resolved in the confirming
direction). SPEC/ARCHITECTURE/DECISIONS/TRACEABILITY: untouched — no requirement, architecture,
or judgment changed; `QUESTION_GENERATION.md` §7 stays accurate (its per-candidate-commit claim
now holds on both duplicate arrival paths). The Frozen Spec was deleted after reconciliation.

**Unresolved handoff items.** (1) RD-01's confirmation (queue row 1) becomes eligible after
tonight's first post-fix nightly firing (~18:01/18:11/18:50 UTC jobs; check from ~19:00 UTC).
(2) Reported, deliberately not widened: a non-duplicate `IntegrityError` on the same path carries
no cost (theoretical today), and REQ-20's row-level attribution residual is unchanged.
(3) The "fail-closed invariants have no pins" three-test package is now fully closed
(REQ-27 → `a3f1511`, SEC-13 → `b6fa067`, COST-06 → `ba660e1`).

**Commits/SHA.** Worktree `d982f32` on `lucasjeongsikpark/cost06-flush-spend`; landed as
`ba660e1` by PR #366.
