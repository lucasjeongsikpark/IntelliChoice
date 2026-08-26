# 2026-08-26 — ARCH-33 read: the deploy gates have fired, census of all 136 runs (D-449)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-449.

A continue request found no new PRs and the queue still empty, so the session executed the
last immediately-executable read the documents name: `gh run list --workflow=deploy-staging.yml`
for `ARCH-33-CI-GATE`.

Result: 136 runs, 122/14. **Both preventive gates have genuinely fired** — the
deployed-version gate blocked run 30884342749 (2026-08-04) and the `/dev/token` security gate
blocked run 30121133594 (2026-07-24). Remaining failures: 6× migrations (first deploy day),
2× build, 1× OIDC, 1× deploy step, 2× cancelled double-dispatch. Every run since 08-11
succeeded. §6.3 row deleted (16 → 15); no code changed.

Handoff unchanged: UD-2 (now also LB-08's measurement window), UD-13, UD-5's EMF promotion,
D310 (a), and the 2026-08-31 07:17 UTC scheduled-controls check.
