# 2026-08-26 — seventeenth Orca run: the learning disconnect spec lands; the template is indicted (D-450)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-450.

The continue took `PLAYWRIGHT-LANE`'s owed artifact (D-427's residual). Executor
(claude/opus/high, liveness-probed): wrote and ran
`e2e/tests/learning/stream-disconnect-visible.spec.ts`, positive direction only, with its own
`student-ext-29` (D-443 convention). Mid-task the executor measured that the Frozen Spec's
`route.abort()` is not terminal for EventSource (1→5 attempts over 12 s idle — a vacuous
reconnect assertion) and asked; the coordinator confirmed the 403 pattern (terminal, and the
documented D-216 case). Landed `26fce8b` (PR #414).

Verification: executor lane 129/2 + failing-direction proof + pytest 1870/2/1 serialized;
coordinator-independent full lane 129/2 exit 0, full capture.

State changes: `PLAYWRIGHT-LANE` deleted (its "lane not executed" half was stale — D-437/443/
444 ran everything — and its residual is done); new row `CHAT-DISCONNECT-VACUOUS` (the
template's own reconnect assertion is likely vacuous under abort, plus its stale
liveness-timer header claim since D-405) — **the queue has one unblocked item again**.

Handoff: the queue item is free local work; UD-2, UD-13, UD-5, D310 (a), and the 08-31 cron
check stand.
