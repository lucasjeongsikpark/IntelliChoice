# 2026-08-23 — standalone session: `DRIFT-86-COST-RUNBOOK` resolved (D-428)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-428.

## What was done

Generic continue request. Queue row 1 (`RD-01`) is time-blocked until after the Sunday
2026-08-24 18:30 UTC run — its own §4.4 note routes an earlier continue to row 2 — so the
session took row 2, `DRIFT-86-COST-RUNBOOK`.

The cost-anomaly playbook in `docs/reference/INCIDENT_RESPONSE.md` told the operator to
"scale `desired_count` to 0", a lever that does not move a live service (`desired_count` is
in `ignore_changes` on `aws_ecs_service`; Application Auto Scaling owns capacity once the
service exists — `terraform/modules/ecs-service/main.tf:370`,
`terraform/environments/staging/main.tf:443-445`). Corrected in place:

- New runbook section "Stopping a live service: `desired_count` is NOT the lever" with the
  working two-call sequence (pin the scalable target min/max to 0 first, then
  `update-service --desired-count 0`), concrete cluster/service names, dated restore values
  (learning-api 2/3, chat-api 1/3 as of 2026-08-23, with the D-344 never-applied caveat),
  and the post-incident `terraform apply` reconciliation step (`F-03-DRIFT-DETECTOR`).
- `BUDGET-GROSS-SPEND` cross-reference added as a caveat on the budget alarm bullet: the
  terraform budget is net-of-credits and currently blind to the ~$250/mo gross run rate
  (as of 2026-08-20); the console-created $10 gross budget is named load-bearing in the
  runbook itself.

Design rationale (CLI-first, min AND max pinned, ordering): D-428.

## Evidence / verification

- `make lint` and `make typecheck`: green.
- `make test`: **1778 passed, 2 skipped, 1 xfailed** (464 s) — green baseline, unaffected by
  the docs-only change.
- The stop sequence was **derived from terraform source and AWS API semantics, not
  executed** — running it would stop a live staging service. Explicitly not live-verified.
- `AUDIT_FINDINGS.md` mentions of `desired_count` are historical finding records, left
  unedited by design.

## Documentation updates

- `docs/PROJECT_STATE.md`: `DRIFT-86-COST-RUNBOOK` deleted from §4.1 (10 → 9 entries,
  16 → 15 total) and from the §4.4 queue (rows renumbered; `WORK-44-DECIDED-NOT-BUILT` is
  now row 2); snapshot header updated. Fan-out check: only the two rows carried the key.
- `docs/DECISIONS.md`: D-428 appended.

## Handoff

- `RD-01` (queue row 1) remains NEXT once time-unblocked: after Sunday 2026-08-24
  18:30 UTC, confirm `JobCompletions{job=memory-consolidate}` publishes and its alarm goes
  ALARM → OK.
- No new open items discovered this session.

Commit: see the docs commit landing this file (docs-only; product code stays `1768c9d`).
