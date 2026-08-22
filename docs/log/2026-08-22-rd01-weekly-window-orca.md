# 2026-08-22 (late) — RD-01 weekly heartbeat window built, corrected against a CloudWatch limit, and applied (fifth Orca run)

Historical narration only — non-authoritative (DQ-1). Current state: `docs/PROJECT_STATE.md`;
durable evidence: `test_scheduled_job_heartbeat_cadence_parity.py`, the per-job window in
`app_events.tf`/`variables.tf`/staging `main.tf`, the live alarm reads, and git history. No new
judgment was made, so no DECISIONS entry exists for this session.

**What was done.** Fifth Orca coordinator/executor run, on PROJECT_STATE §4.4 queue row 1
(the `RD-01` residual: the weekly job's mis-scaled heartbeat). Frozen Spec
`tasks/rd-01-weekly-heartbeat-period.md`; run `run_8ff09e89b7d1`; persistent executor
agent `claude` / model `opus` / effort `high` (receipt: requested == effective). One correction
round — driven by a **platform limit discovered at apply time**, not an implementation error.

**Round 1.** Test-first cadence-parity test (D-385 class; bidirectional — a schedule change
without an alarm change also fails; two test bugs found and fixed while establishing the
baseline: an hourly-cron misclassification and `youtube-sync`'s `var.`-referenced `enabled`).
Terraform: per-job `period` via `lookup(var.job_heartbeat_period_seconds, ...)` with
`memory-consolidate = 1209600` (2 × weekly). Landed as `4669ee2` (PR #369). The coordinator's
targeted apply then **failed on CloudWatch's hard limit**, verbatim: *"ValidationError: Metrics
cannot be checked across more than a week (EvaluationPeriods * Period must be <= 604800) for
alarms using period >= 3600"* — which also invalidated the documented 86400×14 fallback (same
product). The partial apply updated the three daily alarms' descriptions; the weekly alarm was
left untouched.

**Round 2 (correction).** Coordinator-decided adaptation, determined by the constraint and in
the fail-safe direction: the rule becomes **`min(2 × cadence, 604800)`** — the weekly job runs a
7-day window, pages after the *first* missed Sunday (safer for a `retry_attempts = 0` paid-API
job), and cannot flap (every trailing week contains the last Sunday run while healthy). The same
executor lane updated the map (`memory-consolidate = 604800`), all three prose carriers of the
rule, and the parity test (which cites the API error verbatim so nobody re-attempts a longer
window); the invalid fallback text was replaced with an in-cap shape. Landed as `4a5ad20`
(PR #370, the delta from the amended worktree branch `c7256bf`, tree-verified identical).

**Applies and live verification.** Second targeted plan: exactly `0 add / 1 change / 0 destroy`
(the weekly alarm only); applied; read back live: `memory-consolidate` period **604800**, the
three daily alarms period 172800, states OK/OK/OK/ALARM — the weekly ALARM now being **accurate
signal** (no completion in the trailing week; the job's first counted run is Sunday).

**Verification.** Executor: 7/7 parity tests (pre-fix failure recorded both rounds), three
one-sided mutations killed round 1 and one round 2, `terraform fmt`/offline `validate` clean,
`terraform console` render checks, `make lint typecheck test` exit 0 (1766 passed). Coordinator
independently re-ran both parity tests, an override-reverted mutation kill (round 1) and reviewed
the capped-rule delta (round 2), lint, typecheck, fmt-check, plus both plan gates and the live
alarm reads.

**Reconciliation applied.** PROJECT_STATE: snapshot to `4a5ad20` (gap 18), RD-01 row/§4.3/queue
row 1 restated to the Sunday-only confirmation, §8 bullet restated (the weekly ALARM is accurate
signal now). Register: dated "weekly-window fix built and applied" annotation on `RD-01` with the
API error verbatim. ARCHITECTURE: the scheduler note now records the per-job capped window and
the second parity instrument. DECISIONS/TRACEABILITY: untouched — the adaptation is an
engineering response to a hard platform constraint, not a judgment. Frozen Spec deleted.

**Unresolved handoff items.** (1) Queue row 1: after Sunday 2026-08-24 18:30 UTC, confirm
`JobCompletions{job=memory-consolidate}` publishes and ALARM → OK — that closes RD-01 entirely.
(2) Job success stays unproven for all four jobs (completion ≠ correctness). (3) Process note:
the coordinator released the round-1 executor before running the apply gate — the correction
needed a fresh worker in the same worktree; next time hold the release until apply-dependent
acceptance is complete.

**Commits/SHA.** Worktree `e8dfa18` → amended `c7256bf` on
`lucasjeongsikpark/rd01-weekly-heartbeat`; landed as `4669ee2` (PR #369) and `4a5ad20`
(PR #370).
