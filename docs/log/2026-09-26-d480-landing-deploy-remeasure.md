# 2026-09-26 — D-479 landed and deployed (`gha-c2ab834a990e`); collision rate re-measured live at 0 / 10,012 (D-480)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-480.

"proceed" → `land/d479-reset-contextvars`, PR #477, nine checks green first time, rebase-merged
`c2ab834`; deploy run 36217159769 (04:13–04:32 UTC) all gates green, rollback skipped. Post-deploy:
`:158` 2/2, `:156` 1/1, ops `:150`, no command override on the task definitions so the image CMD
with the flag is what runs; edge 401, SPAs 200, 0/0/0 failure signatures.

The live re-measurement needed traffic (staging is idle); asked, and the user authorised a 10k
unauthenticated keep-alive burst. It ran at 69 rps on 16 connections; one target
(`POST /chat/sessions`) returned 200 rather than the 401 the plan assumed — anonymous session
creation is first-class (SPEC §5.19.1) and mints a UUID without persisting anything, so nothing
was written; recorded honestly in D-480. Read-only count from the access log (E6.2's own
metric): **0 shared trace ids** in 5,008 + 5,004 traced lines, against ≈14 predicted by the
pre-fix rate.

Handoff: `OBSERVABILITY-TRACE-GAPS` keeps only `CHECKPOINTER-UNINSTRUMENTED` (queue row 1, low);
next rotation 2026-10-02 (UD-14 open). Scratch scripts for the burst and the counter live only in
this session's scratchpad — not repository code.
