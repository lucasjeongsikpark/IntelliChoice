# 2026-09-25 (fourth entry) — second Orca task: `TRACE-ID-COLLISION` reproduced and closed (D-479)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-479.

"continue" → queue row 1 `OBSERVABILITY-TRACE-GAPS`, the collision half. Understand phase found
the mechanism in primary evidence before any spec was written: uvicorn 0.52.4's
`_start_asgi_task` carries an opt-in `reset_contextvars` branch citing CPython #140947, and its
flow-control code shows both leak paths (pipelined start inside the previous request's task;
`resume_reading()` re-registering the reader with a copy of the current context). Frozen Spec
`tasks/trace-id-collision.md`: reproduce first with a deterministic pipelined raw-socket test,
fix with the documented flag, guard it at source level, no app-level context reset.

Run `run_5641f9a3e94d`, executor `task_df949a141f14` / `ctx_df403493e8a0` (Opus 5.5 high,
receipt matched). One drift returned rather than resolved: the leaked request is an INTERNAL
span, not a SERVER child — sharper than the spec, carried into D-479. Executor `make test`
2259 / 2 / 1; coordinator independent run identical (after killing a self-blocking wait loop
whose `pgrep -f pytest` matched its own command line — recorded here so it is not repeated).
Worker released, no reclaimable terminals. Docs reconciled; Frozen Spec deleted.

Handoff: **implemented locally, uncommitted, not deployed** — the flag reaches the containers
only at the next manual deploy, and the live re-measurement (E6.2 §12 harness on a post-deploy
window) is coordinator-owned follow-up. Queue row 1 remains `OBSERVABILITY-TRACE-GAPS` with
`CHECKPOINTER-UNINSTRUMENTED` only.
