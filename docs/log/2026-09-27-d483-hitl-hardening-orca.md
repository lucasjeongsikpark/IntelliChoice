# 2026-09-27 (second entry) — fourth Orca task: `HITL-INTERRUPT-HARDENING` closed (D-483)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-483.

"proceed" → queue row 1. SPEC §5.1.4 says nothing about how long an approval may wait, so the
TTL half was a product decision: asked the user (24 h auto-decline / 7 d / no expiry by design)
— **24 h auto-decline for external-action pauses, selection pauses exempt.** The serialization
half was engineering: an allowlist test over every graph call site rather than a refactor.

Run `run_73459cd4bb2e`, executor `task_f593a8484515` / `ctx_d19068660b4a` (Opus 5.5 high,
receipt matched). Two questions came back as findings, both answered as spec revisions:
learning's gate has nine callers and claims after the read (Revision 1: only the four mutation
routes auto-decline, claim + re-read on the expiry path only); `test_turn_deadline.py` pinned
"seven" call sites (Revision 2: 8, renamed). Executor `make test` 2301 / 2 / 1; coordinator
independent run identical. Worker released, no reclaimable terminals.

Docs: SPEC §5.1.4 amended in place with a dated marker + index line; D-483; D-459 pointers;
PROJECT_STATE row deleted, queue advanced; ARCHITECTURE turn-claim bullet extended. Frozen
Spec and report deleted. **Implemented locally, uncommitted, not deployed.** Queue row 1 is now
`CONTENT-GATE-HINT-COHERENCE` residuals — half of which is a USER content decision.
