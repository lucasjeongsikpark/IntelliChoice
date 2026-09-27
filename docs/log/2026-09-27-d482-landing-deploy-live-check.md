# 2026-09-27 — D-481 landed and deployed (`gha-f05c38132555`); checkpoint span seen live (D-482)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-482.

"proceed" → `land/d481-checkpointer-spans`, PR #479, nine checks green first time, rebase-merged
`f05c381`; deploy run 36341554484 (18:41–19:00 UTC) all gates green, rollback skipped.
Post-deploy: `:159` 2/2, `:157` 1/1, ops `:151`, edge 401, SPAs 200, 0/0/0 failure signatures.

Live check without spend: an anonymous session mint plus a 6-second anonymous stream connect
(the route calls `graph.aget_state`; a fresh session answers 404). Its X-Ray trace carries the
checkpointer's `select thread_id, checkpoint, checkpoint_ns …` subsegment — the first checkpoint
I/O ever visible in a staging trace. The X-Ray reader script was dry-run first on yesterday's
burst window (3,646 chat traces, 0 with SQL — those routes touch no DB), so "found one" is a
detection, not a default.

Handoff: `OBSERVABILITY-TRACE-GAPS` is fully closed; queue row 1 is `HITL-INTERRUPT-HARDENING`;
next rotation 2026-10-02 (UD-14 open).
