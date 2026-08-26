# 2026-08-26 — eighteenth Orca run: the chat reconnect assertion can fail now (D-451)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-451.

The continue took `CHAT-DISCONNECT-VACUOUS`. Executor (claude/opus/high, liveness-probed):
measured the abort-vacuity in chat's own harness first (abort: 1→4 attempts over 12 s idle,
button never clicked; 403: 1→1→2 — D-450's numbers reproduced), converted the spec to the 403
pattern, tightened `audit.allow`, rewrote the header's two stale claims (both apps have D-405's
liveness timer; only a non-2xx is terminal), corrected one contradicted hook-comment clause,
and proved the failing direction with a temporary spec (403 form fails without the click;
abort form passes). Landed `825ce76` (PR #416).

Verification: executor lane 129/2 exit 0 + pytest 1870/2/1 serialized + chat-web unit suite;
coordinator-independent full lane 129/2 exit 0, full capture.

One CI flake recorded (n=1, rerun green): the D-433 SSE-over-HTTP test failed once with
`KeyError: 'phase'` on a PR that does not touch it; signature and fix direction are in D-451.

State changes: `CHAT-DISCONNECT-VACUOUS` deleted; the two out-of-scope residuals queued as
`DISCONNECT-NITS` (two-line-diff scale, the queue's one unblocked item); header at `825ce76`
(gap 2, test-side only).

Handoff: `DISCONNECT-NITS` is free local work; UD-2, UD-13, UD-5, D310 (a), and the 08-31
cron check stand.
