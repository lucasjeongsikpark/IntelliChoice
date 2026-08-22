# 2026-08-22 (evening) — RD-01 nightly confirmation observed; weekly-period defect surfaced

Historical narration only — non-authoritative (DQ-1). Current state: `docs/PROJECT_STATE.md`;
durable evidence: the live CloudWatch reads below (control-plane facts, dated) and git history.
No new judgment was made, so no DECISIONS entry exists for this session.

**What was done.** Queue row 1 (`RD-01` confirmation) became eligible when the day's nightly jobs
fired. This was a read-only verification, performed directly by the coordinator (no Orca
executor — nothing to implement). All reads under `jeongsik-staging-admin`, 2026-08-22 UTC
evening, against the live staging account (control-plane; no image change — staging still runs
`gha-44a12dfc9549`).

**What was observed.**

- The three nightly jobs fired on schedule (log streams and structured events at 18:00 / 18:10 /
  18:50 UTC). `session_consolidate_job_complete` was read back verbatim from
  `/ecs/intellichoice-staging-ops-task`: underscored `event`, hyphenated `job`, real counts
  (`threads 5623, written 0, skipped_not_learning 2711, unchanged 2912`).
- `JobCompletions` published its **first-ever datapoints** — one per nightly `job` dimension, in
  `IntelliChoice/intellichoice-staging/pipeline` — after fourteen days of zero.
- Three heartbeat alarms transitioned **ALARM → OK** the same evening: `chat-purge` 19:05:51Z,
  `retention-purge` 19:11:05Z, `session-consolidate` 19:42:40Z. Long-period (172800 s) alarms
  evaluated ~1–1.7 h behind their datapoints; a background poll caught the last flip.
- **New defect surfaced:** `memory-consolidate` is a weekly job (`cron(30 18 ? * SUN *)`,
  `terraform/modules/scheduled-jobs/main.tf:91`) listed in `nightly_job_events` under the uniform
  two-day heartbeat period (`app_events.tf:225`). Its alarm cannot confirm before Sunday, and
  once it does it will be OK ~2 days then re-enter ALARM for the rest of every week — permanent
  weekly page-channel flapping, previously masked because the alarm never left ALARM at all.
  ARCHITECTURE knew the job was weekly and the register verified the alarm matches the filter;
  no document had connected the two facts.

**Reconciliation applied.** PROJECT_STATE: `RD-01` row, §4.3 paragraph and §4.4 queue row 1
restated from "confirmation" to the weekly-period fix (terraform, apply-only; confirm after the
first post-fix Sunday run); §3's consequence line and the §8 headline bullet updated to the
confirmed state (one mis-specified instrument remains); `C6-UNATTENDED`'s clock note (nightly
three run from 2026-08-22, earliest satisfiable 2026-08-29); `WORK-23`'s prerequisite marked
half met (the session-consolidate firing record now exists); `F4-CRITERION6` detectability dated.
Register: dated step-(c) confirmation annotation on `RD-01`, including the new weekly-period
finding and its replacement remaining action. ARCHITECTURE: the scheduler-note passage updated to
the confirmed state plus the mis-specified-instrument fact. DECISIONS/TRACEABILITY: untouched.

**Unresolved handoff items.** (1) Queue row 1 is now the `memory-consolidate` heartbeat-period
fix — startable immediately (apply-only), with its own confirmation gated on the first post-fix
Sunday 18:30 UTC run. (2) Job **success** remains unproven for all four jobs: the events report
completion counts, not correctness. (3) `C6-UNATTENDED`'s seven-day unattended window for the
nightly three is earliest satisfiable 2026-08-29.

**Commit/SHA.** Docs-only session; no product-code change. Staging image unchanged
(`gha-44a12dfc9549`); the observed behaviour is the 2026-08-21 control-plane apply working as
intended.
