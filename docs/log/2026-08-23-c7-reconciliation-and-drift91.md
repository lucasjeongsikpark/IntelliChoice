# 2026-08-23 — WORK-12-BANNER reconciled to D-417 §C7 (D-427); DRIFT-91 resolved (eighth Orca run)

Historical narration only — non-authoritative (DQ-1). Current state: `docs/PROJECT_STATE.md`;
the judgment record for the reconciliation is **D-427**; DRIFT-91's evidence is git history and
the tests named below.

**Part 1 — the eligibility gate caught a decision conflict.** Queue row 1 (RD-01's Sunday
confirmation) was time-blocked, and row 2 (`WORK-12-BANNER`, "write the banner test by mocking
`useLearningSession`") **failed the gate**: the register entry itself mandates reading
D-417 §C7's scope, and the read shows C7 is explicit, specific and considered — *"Decided. No
mock-heavy `useLearningSession` test for this one condition"* — the user's same-day answer to
D-414's carry-over pricing, not scope drift. The register cannot override an accepted decision
by its own charter (*"evidence, never authority for intent"*). Recorded as **D-427** (an
application of existing authority, not a new judgment): the `App.tsx` in-code status is
accurate; the archived `PROGRESS.md` carry-over line is the retracted loser; the C7-consistent
residual (a positive-direction browser spec mirroring chat-web's
`stream-disconnect-visible.spec.ts`) is folded into `PLAYWRIGHT-LANE`, to be written **and run**
in the next serialized lane window. The `WORK-12-BANNER` rows were removed as
conflicting-with-decision, not as done.

**Part 2 — the newly valid first eligible row: `DRIFT-91-ORGTIME-IMPORT`.** Eighth Orca run
(run `run_83fe66244951`, tasks `task_6a14be858009` + correction `task_faf0621b3332`, same
persistent executor terminal across both; agent `claude` / model `opus` / effort `high`,
receipts requested == effective). `current_week_key` — pure org-calendar logic (SPEC §5.6.2)
that lived in the MySQL adapter module — moved to `intellichoice_shared.org_time` with no
compatibility re-export; six importers updated, including `load-tests/loadtest_fixtures.py`
(outside the spec's enumeration — flagged by the executor, not silently expanded);
`test_week_key_convention.py` followed the symbol to `packages/shared/tests/`. The optional
adapter factory was deliberately skipped (an empty pass-through; env selection stays D-002's
integration-time work). One correction round fixed the moved docstring's self-reference and
relocated the test file — as a separate commit so the reviewed first commit stayed intact.

**Evidence.** Behavior byte-identical: full suite 1778 passed / 2 skipped / 1 xfailed both
before and after (zero delta); acceptance grep shows only the `MySQLProfileAdapter` class
imported from the adapter module in `apps/`; lint/typecheck clean. Coordinator independently
re-ran the moved and adjacent test files (148 passed), lint, typecheck. Landed by PR #377 as
`0cadc94` + `1768c9d` (12/12 CI).

**Reconciliation applied.** DECISIONS: D-427 appended. PROJECT_STATE: `WORK-12-BANNER` rows
removed per D-427 (counts 18→17, 7→6) and `DRIFT-91` rows deleted on resolution (17→16, 11→10);
queue renumbered (15 rows; row 1 stays RD-01's Sunday confirmation); `PLAYWRIGHT-LANE` row
carries the re-homed browser-spec residual; snapshot to `1768c9d` (gap 4 product commits — the
date-zone pair plus the behavior-identical relocation). Register: the mandated-read annotation
on `WORK-12-BANNER` and the resolution annotation on `DRIFT-91-ORGTIME-IMPORT`.

**Unresolved handoff items.** (1) Queue row 1: RD-01's Sunday 2026-08-24 18:30 UTC
confirmation. (2) The 4-commit deploy gap (say "deploy" to close it). (3) The learning-web
disconnect browser spec waits for the next Playwright lane window (D-427). (4) If the user ever
wants the mock-test route for the banner after all, that is an explicit reversal of D-417 §C7 —
never inferred.

**Commits/SHA.** Worktree `edf132d` + `ca4dbb9` on `lucasjeongsikpark/drift91-orgtime`; landed
as `0cadc94` + `1768c9d` by PR #377.
