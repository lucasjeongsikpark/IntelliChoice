# 2026-09-25 (second session) — first Orca coordinator/executor task: `MEMORY-CACHE-WRITE-UNBILLED` fixed (D-476)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-476.

User: "continue; this Fable session coordinates, an Opus 5.5 session executes, per CLAUDE.md".
Loaded `orca skills get orchestration --full`, `orca status` ready. Queue row 1 was
`MEMORY-CONSOLIDATION-DEFECTS` #4; eligibility gate passed (open, engineering-owned, no UD).

Understand phase from primary evidence, not the report summary: `_cost_cents` prices
`inputTokens` only while a cold cached call reports its payload under `cacheWriteInputTokens`;
the failure exits were handed `(input, output)` only; D-203's first-user cache point cannot be
read without a tool loop (one round; the D-217 repair changes the user text), and consolidation's
≈249-token system prompt is under the cacheable minimum, so the unique payload was written to the
cache every call and read never. Frozen Spec `tasks/memory-cache-write-unbilled.md` with five
coordinator decisions (multipliers 1.25/0.1; one `_Usage` value to every exit; conservative
reservation/admission; provider rule "first-user cache point only with tools"; comment).

Run `run_5bb9e2d4e019`, executor `task_dc4dd2825946` / `ctx_67ae312fde8b`, launch receipt
requested == effective (claude-opus-5-5, high). Streaming `check --wait` was not used; a 30 s
`check --peek` poll loop plus the Orca message notifications worked. The executor returned one
spec/code conflict correctly (three app reservation constants under-reserve under D3 and their
guard tests exist to catch that) → spec Revision 1 extended Scope and set 2.5 / 4.5 / 26.0.
`worker_done` with the full evidence shape; coordinator review of the actual diff found it
matching the spec; independent full run **2253 / 2 / 1** matched the executor's. One drifted
comment outside Scope fixed by the coordinator. Worker released; no reclaimable terminals.

Handoff: row restated as user-gated (UD-15 ceiling bound, UD-2 measurement) and out of the
queue; row 1 is now `OBSERVABILITY-TRACE-GAPS`. **Implemented locally, uncommitted, not
deployed** — staging is `gha-61fc8a528418`. Frozen Spec deleted per contract.
