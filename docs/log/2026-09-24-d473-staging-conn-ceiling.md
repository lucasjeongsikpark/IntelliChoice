# 2026-09-24 — D-472 and the CLAUDE.md operating model committed; `STAGING-CONN-CEILING` fixed (D-473)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-473.

Session opened on the previous session's entire output still uncommitted (D-472's three product
files, five tests, docs and R6 evidence; the CLAUDE.md Orca operating-model rewrite). Baseline
before any edit: lint/typecheck clean, 2231/2/1 — identical to D-472's close. With the user's
go-ahead both landed as two commits (`fea58e2` CLAUDE.md, `c90fce7` D-472) so this session's diff
stays separable.

Took §4.4 row 1, `STAGING-CONN-CEILING`, after the eligibility gate. Root cause re-derived from
code rather than the E1 report's summary: 23 connections per API task (10 + 10 pool, 2 relay, 1
checkpointer — `from_conn_string` is a single connection, not the "pool" S34 called it), six API
tasks at the replica ceilings, plus the ops task, against ~109 slots. The user chose pool 5 + 5
per task over lowering the replica ceiling; budget 98 ≤ 109 with the two overlappable ops
schedules counted. Engine constants + `connection_budget()` in one place, settings-driven
passthrough in both apps, and a test that parses the terraform replica ceilings so a capacity
bump fails locally. No terraform change.

Mid-session Docker Desktop's daemon stopped (socket gone, 5432 refused) — restarted and the
compose stack brought back up; the previous session's log records the same thing. Verification:
ruff/pyright clean, focused 27 passed, full suite **2241 passed / 2 skipped / 1 xfailed** (baseline 2231 + 10 new tests).

Handoff: row deleted from §4.1, queue advanced (memory #4 cost accounting is row 1). **Implemented
locally, not deployed** (LB-05) — staging is still `523b9f0`, two product commits behind
once this lands. UD-14: no AWS read this session either; rotation windows ~09-04, ~09-11, ~09-18
have passed unchecked.
