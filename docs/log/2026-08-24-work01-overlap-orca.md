# 2026-08-24 — twelfth Orca run: D-423's overlap built (D-441)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-441.

## Workflow

Frozen Spec (`tasks/work01-scope-guard-overlap.md`) → first executor launch **dead on
arrival** (Orca runtime restart around the dispatch; 103 min of `dispatched` with zero
heartbeats/output/session/file-changes — **caught by the user**, not by the coordinator's
loop) → explicit recovery (`task-update → ready`, fresh attempt, liveness probe before trust)
→ verified-live executor (claude/opus/high, `ctx_2375d08b542d`) → worker_done → coordinator
review (join fold, §5.30-conscious error handling, degraded×retrieval matrix probed; 111
focused tests + gates re-run) → one docstring correction round → acceptance → landed
`5b67e04` (PR #403) → this reconciliation. New standing convention: every `worker-start` gets
a liveness probe.

## Highlights

- Grounded turns: four sequential Bedrock calls → three (`scope_guard` ∥ `retrieve_context`,
  join, synthesis) with zero prompt/model/threshold/filter changes. ~22% median per D-423's
  staging baseline; **not re-measured** (UD-2), and the recorded span mapping is mandatory
  for the future comparison (summing spans now double-counts).
- Channels split, not reducer-ed (every node writes spend as absolute totals; the
  `InvalidUpdateError` was confirmed empirically first); the join settles billed spend on
  every path including discarded ones, pinned by a price-it-twice test.
- The wasted branch fails quiet (a speculative DB error cannot take down a calendar turn);
  the needed branch fails closed exactly as before; only exception class names enter the
  checkpoint (SPEC §5.30).
- Cross-version resume verified both directions (InMemorySaver; production saver recorded as
  residual). Suite 1867/2/1 (+53).

## State changes

- `WORK-01-SCOPE-GUARD` deleted from §4.2 and the queue (`WORK-35-LEDGER` is now row 1);
  ARCHITECTURE's D-423 bullet and the chat-graph Mermaid rewired to the fan-out/join
  topology; §3's LB-08 note restated (built at HEAD, comparison is future UD-2 work);
  D-438's trigger fired a third time, skip-noted; header at `5b67e04` (gap 21).

## Handoff

- Next queue item: `WORK-35-LEDGER` — the free staging measurement, then the U7 design
  review (now also carrying D-440's `existing_facts` crossover input).
- A future deploy ships eight accumulated improvements; the first staging latency
  measurement after it answers whether ~7.5 s materialised.
- Standing user items: UD-13, UD-5's EMF promotion, D310 (a).
