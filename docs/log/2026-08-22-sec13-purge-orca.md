# 2026-08-22 — SEC-13-PURGE resolved (third Orca coordinator/executor run)

Historical narration only — non-authoritative (DQ-1). Current state: `docs/PROJECT_STATE.md`;
durable evidence: the three new tests in `apps/chat-api/tests/test_chat_endpoints.py`, the
`finally`/`session_scope` purge in `sessions.py`/`checkpoint_privacy.py`, and git history. No new
judgment was made, so no DECISIONS entry exists for this session.

**What was done.** Third Orca coordinator/executor run, on PROJECT_STATE §4.4 queue row 1
(`SEC-13-PURGE`). The coordinator verified the eligibility gate (register entry vs. primary
evidence at `7eb6c73`), identified the rolled-back-purge trap up front (`get_db_session` commits
only on the normal path, so a naive same-session `finally` purge is undone exactly on the
exception path), froze the task as `tasks/sec-13-purge-cancel-exception-paths.md`, and dispatched
it through Orca (run `run_51d724d16191`, task `task_9d84a87ebc3f`, dispatch `ctx_e6d14fdf433c`)
to a persistent executor launched as agent `claude`, model `opus`, effort `high` — requested and
effective identical in the launch receipt. Zero correction rounds.

**What the executor delivered.** Test-first: both leak paths demonstrated failing against
committed Postgres state (the msgpack lat/lon visible in the failure output) — a cancelled
location-consent resume via the real cooperative-cancellation mechanism, and an injected
mid-resume failure with a reached-the-node control. Fix: the purge moved into a `finally`
covering all four turn endings, running on its own `session_scope` unit of work (the codebase's
existing factory convention — `get_cost_ledger`, `get_turn_cancellations`,
`get_escalation_sends`), because `AsyncPostgresSaver`'s `autocommit=True` connection commits the
coordinates independently of the request transaction. An asymmetric vacuity control proved the
point: with the purge moved back onto the request session, the exception-path test fails while
the cancel-path test passes. A third test pins that a failed resume stays retryable (no
functional regression from purging a failed turn's resume value).

**Evidence.** Executor: pre-fix 2 failed (the leak), post-fix 6 passed (2 new + 4 success-path
unchanged), retry test passed, chat-api 273 passed / 1 skipped, `make lint`/`typecheck`/`test`
exit 0 (1760 passed / 2 skipped / 1 xfailed). Coordinator independently re-ran the focused tests
(7/7), a no-op-purge mutation kill (6 failed as predicted, reverted, tree clean), lint,
typecheck, and the chat-api suite before accepting.

**Landing.** Worktree commit `a54101c` cherry-picked to `land/sec13-purge-paths` (tree verified
identical), landed by PR #364 into protected `main` as `b6fa067` after all 12 CI checks passed.

**Reconciliation applied after acceptance.** PROJECT_STATE: §4.1 row and §4.3 paragraph deleted
(counts 25→24, 15→14; §4.3 now "four items"), the §4 "by code reading" sentence narrowed to
`COST-06-FLUSH` alone, §4.4 row deleted and the queue renumbered (RD-01's time-blocked
confirmation is row 1 with a gate note; `COST-06-FLUSH` is the first work-startable row), snapshot
header advanced to `b6fa067` (gap 15). Register: loud dated resolution annotation on
`SEC-13-PURGE` (original text kept); a dated LB-05 note on `G2-LOCATOR-PURGE` (a staging probe
means different things before/after the next image deploy). TRACEABILITY §5.1.3: stale anchor
fixed (`checkpoint_privacy.py:24`→`:35`) and the row strengthened with the dated
cancel/exception-path evidence. ARCHITECTURE/SPEC/DECISIONS: untouched — no architecture change,
no requirement change, no new judgment. The Frozen Spec was deleted after reconciliation.

**Unresolved handoff items.** (1) Staging still runs the defective code until the next image
deploy (UD-1); rows already leaked on live staging threads are not swept — that is
`RETENTION-CLUSTER` / UD-7, a user decision. (2) A deliberate consequence, recorded in the code
comment: a 503 ceiling refusal on a location resume now also issues the (no-op) DELETE. (3) A
hard task-cancellation of the handler mid-`finally` is not defended against, on D-402's measured
basis that uvicorn does not cancel this handler; the basis is recorded in the comment. (4) RD-01's
confirmation (queue row 1) stays time-blocked until tonight's first post-fix nightly firing.

**Commits/SHA.** Worktree `a54101c` on `lucasjeongsikpark/sec13-purge-paths`; landed as
`b6fa067` by PR #364.
