# 2026-09-26 (second entry) — third Orca task: `CHECKPOINTER-UNINSTRUMENTED` closed (D-481)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-481.

"continue" → queue row 1, the last `OBSERVABILITY-TRACE-GAPS` item. Understand phase: psycopg is
the checkpointer's driver and nothing else's in the apps; the standard
`opentelemetry-instrumentation-psycopg` 0.65b0 (same contrib release as the two instrumentations
in use) wraps psycopg 3's async connection — verified in a throwaway env before the spec. Frozen
Spec `tasks/checkpointer-uninstrumented.md`: standard instrumentor over a hand-written saver
wrapper, module-level call before the lifespan opens the connection, parameters never captured,
proof against the real saver on the dev Postgres with a payload marker that must reach the DB
and no span.

Run `run_eb99703d4f3f`, executor `task_9e98c72e4a21` / `ctx_16d8ba92af61` (Opus 5.5 high,
receipt matched). No questions, no conflicts; the executor added a negative control (parameters
captured → marker leaks) that proves the absence assertion is not blind, and wrote its report
inside the checkout this time (`tasks/…report.md`, deleted with the spec). Executor `make test`
2262 / 2 / 1; coordinator independent run identical. Worker released, no reclaimable terminals.

Handoff: **implemented locally, uncommitted, not deployed** (the instrumentor reaches the
containers at the next deploy; a checkpoint span in a live X-Ray trace is the live check). The
E6.2 harness would count psycopg spans as the SQLAlchemy hop — recorded in D-481 as a caveat for
any re-run. Queue row 1 is now `HITL-INTERRUPT-HARDENING`.
