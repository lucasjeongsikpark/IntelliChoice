# 2026-08-21 — REQ-27-FROZENSET resolved (first Orca coordinator/executor pilot)

Historical narration only — non-authoritative (DQ-1). Current state: `docs/PROJECT_STATE.md`;
durable evidence: `packages/shared/tests/test_auth_consent_gate.py` and git history. No new
judgment was made, so no DECISIONS entry exists for this session.

**What was done.** First run of the Orca coordinator/executor workflow on this repository.
The coordinator investigated `REQ-27-FROZENSET` (register lines 475–508, PROJECT_STATE §4.2),
froze the task as `tasks/req-27-frozenset-pins.md`, and dispatched it through Orca
(run `run_51f5a5f69f3d`, task `task_b75a9f3129b1`, dispatch `ctx_0039f858df2d`) to a persistent
executor launched as agent `claude`, model `opus`, effort `high` — requested and effective
identical in the launch receipt. The executor created
`packages/shared/tests/test_auth_consent_gate.py` (14 tests; the only file changed) and reported
completion evidence per the contract, including `New Decision Required: none`.

**Evidence produced.** Focused pytest 14 passed; mutation check: injecting a value into
`AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` failed exactly the emptiness pin (1 failed /
13 passed — the pre-existing suite was green under a fail-open COPPA mutation), revert
checksum-verified; `make lint` and `make typecheck` exit 0; `make test` exit 0 with
1749 passed / 2 skipped / 1 xfailed in 8m37s. The coordinator independently re-ran the focused
suite, lint, typecheck, and the mutation kill before accepting. Zero correction rounds.

**Reconciliation applied after acceptance.** PROJECT_STATE: §4.2 row deleted (counts 27→26,
11→10), `REQ-27-FROZENSET` removed from the §4 by-code-reading list, and the
`DRIFT-70-CONSENT-GATE` carve-out reversed, citing the test file as the resolution evidence.
Register: loud dated resolution annotation on the `REQ-27-FROZENSET` entry (original text
kept), citing the executable test. DECISIONS: untouched — executor and coordinator both
concluded `New Decision Required: none`, and an implementation completion is not a judgment,
so no D-number was created. TRACEABILITY: untouched — its claim universe contains no REQ-27
rows (verified by grep), so no row was owed.

**Unresolved handoff items.** (1) `SEC-13-PURGE` and `COST-06-FLUSH` — the other two thirds of
the "fail-closed invariants have no pins" package — remain open in PROJECT_STATE §4.1.
(2) `make up` collides on fixed host ports inside an Orca worktree while the main checkout's
compose stack is up (first collision: 9090); the executor ran against the main stack's healthy
dev databases and removed only the stray never-started worktree compose project (main stack
verified intact). Recorded here only, as an orchestration-ergonomics observation — not fixed,
not promoted to a decision. (3) The accepted test commit was `00f6886` in the Orca pilot worktree, cherry-picked locally as
`5cc2141`, then rebased by PR #359 into protected `main` as `a3f1511`; PROJECT_STATE §1
uses `a3f1511` as the current repository product-code baseline.

**Commit/SHA.** `00f6886` in the Orca pilot worktree; cherry-picked locally as `5cc2141`,
then rebased by PR #359 into protected `main` as `a3f1511`.
