# DEPLOYED_INFRA_DRIFT_REGISTER.md — Phase 3B-1 runtime drift register

**Date:** 2026-08-19. **Observation window:** 2026-08-19T22:00Z – 2026-08-20T00:30Z (the three
inspector lanes executed between 2026-08-20T00:03Z and 2026-08-20T00:13Z). AWS account `3205…`,
region `us-east-1`, profile `jeongsik-staging-admin`, strictly read-only. **Zero `AccessDenied`
across all three lanes.**

Companion to `DEPLOYED_INFRA_STATE_EVIDENCE.md` (same directory), which carries the per-claim
evidence and the coverage accounting. This file records **repository-vs-runtime and
intent-vs-runtime mismatches only. It fixes nothing and decides nothing.** Where an inspector's
self-chosen severity differed from the Phase 3B-1 adjudication, the adjudication's ruling is used
verbatim; the **Severity** field, not the id, is authoritative.

Sibling register: `REPOSITORY_DRIFT_REGISTER.md` (Phase 3A, `DRIFT-*` ids) records
documented-intent-vs-repository drift. This register's ids are `RD-*` and its second term is
always the **deployed** system.

## 1. How to read this register

**HIGH** means a control believed to be working is not working, or an operator acting on the
current documents would be wrong about live state. **MEDIUM** means materially misleading, or a
live accepted risk that needs an owner decision — wrong to rely on, but not a broken control.
**LOW** is precision and cost noise: revision numbers, unbilled-until-later line items, expected
pre-integration absences.

Two fields close each entry. *Phase 3B-2 behavioral verification still needed?* asks whether a
browser walk, an HTTP probe or a local suite run could add anything the control plane could not —
several entries are already settled at this layer and need nothing further. *Genuine decision
required?* asks whether closing the entry needs a judgement (money, security posture, launch
posture) rather than a mechanical fix; where it is **YES** the entry names the question and does
not answer it.

Email local-parts are masked. No secret value, or any fragment of one, appears in this file;
`get-secret-value` was never issued. Secrets Manager **version identifiers** are AWS-generated
opaque names, not secret material.

Entries are ordered HIGH → MEDIUM → LOW.

## 2. Entries

### HIGH

- **Runtime Drift ID**: RD-01
- **Title**: The nightly-job dead-man's switch is structurally non-functional — the deployed metric-filter pattern and the Python event name can never match
- **Related claims**: COST-18, COST-19, WORK-35, ARCH-04 / **Related decisions**: D-377 (the `*_job_complete` record and the heartbeat pair), D-385-class (the cross-boundary parity test)
- **Intended state**: A nightly job that silently stops running is detected without anyone watching. Each enabled job emits a structured `*_job_complete` record at the end of its `main()`; a CloudWatch metric filter over the ops-task log group turns that record into a `JobCompletions` datapoint dimensioned by `job`; a heartbeat alarm (`LessThanThreshold 1`, `Sum`, `period = 172800`, `treat_missing_data = "breaching"`) therefore reads **OK** while the job completes nightly and **ALARM** only when it has not completed for two days. The deliberate absence of `default_value` is load-bearing: with a dimension, a job that never ran emits no series at all, and "no datapoint" is exactly the breaching condition.
- **Repository state**: The two sides spell the event differently.
  - `packages/observability/src/intellichoice_observability/scheduled_jobs.py:61` emits an **underscored** name: the job key `session-consolidate` becomes `session_consolidate_job_complete`. The hyphenated job keys it starts from are at `:39-43`, with the comment at `:37-38` recording that they are hyphenated "because that is what `locals.jobs` uses and what the alarm's `job` dimension will match".
  - `terraform/modules/observability/app_events.tf:173` builds the filter pattern from the **hyphenated** `each.key` (`for_each = toset(var.nightly_job_events)` at `:170`), so the pattern searches for `session-consolidate_job_complete`. The four keys are passed from `terraform/environments/staging/main.tf:777-782`.
  - So the filter is correct against the terraform key and the emitter is correct against nothing the filter looks for. Every other attribute of the pair — period, threshold, statistic, dimension, treat-missing-data, routing — matches the config exactly. The instrument is exactly as written and cannot work.
- **Deployed state** (UTC 2026-08-20T00:04:48Z – 00:06:02Z):
  - All four `nightly_jobs` filters exist on `/ecs/intellichoice-staging-ops-task`, patterns verbatim and **hyphenated**:
    `{ $.event = "session-consolidate_job_complete" }`,
    `{ $.event = "chat-purge_job_complete" }`,
    `{ $.event = "retention-purge_job_complete" }`,
    `{ $.event = "memory-consolidate_job_complete" }`
    — each → `IntelliChoice/intellichoice-staging/pipeline / JobCompletions`, `value=1`,
    `default=ABSENT`, `dims={"job":"$.job"}`.
  - `list-metrics` on `IntelliChoice/intellichoice-staging/pipeline` returns **7** metrics —
    `CurriculumTemplates{Created,Retired,Updated}`, `Pipeline{Cost,Filled,Rejected,StoppedEarly}` —
    and **`JobCompletions` is not among them.**
  - `get-metric-statistics` for `JobCompletions` over 14 days, per `job` dimension:
    `session-consolidate {"datapoints":0}`, `chat-purge {"datapoints":0}`,
    `retention-purge {"datapoints":0}`, `memory-consolidate {"datapoints":0}` — **zero datapoints
    ever, on all four.**
  - All four heartbeat alarms are in **ALARM** and have **exactly one state transition each in
    their entire history**, `INSUFFICIENT_DATA → ALARM`:
    `job-chat-purge-heartbeat` 2026-08-16T23:15:15Z, `job-memory-consolidate-heartbeat`
    2026-08-16T23:27:54Z, `job-session-consolidate-heartbeat` 2026-08-16T23:49:48Z,
    `job-retention-purge-heartbeat` 2026-08-17T00:04:18Z. **No heartbeat alarm has ever been in
    `OK`.** `StateReason` is identical and verbatim on all four:
    `"Threshold Crossed: no datapoints were received for 1 period and 1 missing datapoint was treated as [Breaching]."`
    `ActionsEnabled: true` on all four; `AlarmActions` and `OKActions` both
    `arn:aws:sns:us-east-1:3205…:intellichoice-staging-alerts` (the page channel, whose email
    subscription is confirmed).
  - **The jobs do run.** `/ecs/intellichoice-staging-ops-task` carries log streams at **18:01,
    18:11 and 18:50 UTC on both 2026-08-18 and 2026-08-19** — one stream per invocation, matching
    the `cron(0 18 …)` / `cron(10 18 …)` / `cron(50 18 …)` schedules. Stream **metadata only**;
    no stream content was read.
  - Cross-check that the ops-task structured-record path works in general: the seven
    `curriculum-*` / `pipeline-*` metrics fed by the same log group's other filters **do** carry
    data. Whatever is missing is specific to the nightly `*_job_complete` line.
- **Evidence**:
  - `aws logs describe-metric-filters --log-group-name /ecs/intellichoice-staging-ops-task`
  - `aws cloudwatch list-metrics --namespace IntelliChoice/intellichoice-staging/pipeline`
  - `aws cloudwatch get-metric-statistics --namespace IntelliChoice/intellichoice-staging/pipeline --metric-name JobCompletions --dimensions Name=job,Value=<job> --start-time <-14d> --end-time <now> --period 86400 --statistics Sum` (×4)
  - `aws cloudwatch describe-alarms --alarm-name-prefix intellichoice-staging-job-`
  - `aws cloudwatch describe-alarm-history --alarm-name intellichoice-staging-job-<job>-heartbeat --history-item-type StateUpdate --max-records 20` (×4)
  - `aws logs describe-log-streams --log-group-name /ecs/intellichoice-staging-ops-task --order-by LastEventTime --descending` (metadata only)
  - The two mismatched source lines, quoted verbatim:
    - `packages/observability/src/intellichoice_observability/scheduled_jobs.py:61` —
      `f"{job.replace('-', '_')}_job_complete"`
    - `terraform/modules/observability/app_events.tf:173` —
      `pattern = "{ $.event = \"${each.key}_job_complete\" }"`
- **Severity**: HIGH
- **Consequences to record** (recorded, not acted on):
  1. **The switch cannot distinguish a dead job from a healthy one.** It sits permanently in
     ALARM either way, so the alarm carries no information about the thing it was built to watch —
     and four page-channel emails per state change have already been delivered to the single
     mailbox since 2026-08-16.
  2. **Job execution is confirmed at the metadata level; job SUCCESS remains unproven.** The
     18:01/18:11/18:50 streams prove invocation, not outcome — the streams could equally hold
     tracebacks. Reading them is an ops log-content read, not a browser test.
  3. **WORK-35's "≥1 week unattended" criterion cannot be measured by this instrument until the
     mismatch is fixed**, independently of LANE-C's arithmetic point (schedule created
     2026-08-16T04:10:34Z → at most four firings so far → earliest possible satisfaction
     2026-08-23T18:00Z).
  4. **No local test asserts terraform-pattern ↔ Python-event-name parity** — exactly the
     cross-boundary class the D-385 parity test was invented for.
     `packages/observability/tests/test_alarm_severity_routing.py` cannot catch it: it routes
     alarms, it does not match patterns.
- **Phase 3B-2 behavioral verification still needed?**: **no** — settled at this layer; the only
  thing left unproven is job *success*, which is an ops read of log content, not a browser test.
- **Genuine decision required?**: **NO** — a one-line mechanical fix on either side (emit
  hyphenated, or build the pattern from an underscored key). Recorded here, not fixed.

### MEDIUM

- **Runtime Drift ID**: RD-02
- **Title**: The two staging-token shared secrets were never rotated after the D-310 process-table exposure, and the exposed values are still `AWSCURRENT` and actively read
- **Related claims**: SEC-26 / **Related decisions**: D-310
- **Intended state**: D-310 recorded a **declined** rotation after the 2026-08-13 process-table exposure of the two `/dev/token` staging shared secrets. So the intended state is "not rotated, knowingly" — the open question is whether that decline still holds six days on, with the exposed values live.
- **Repository state**: No rotation mechanism exists and none ever did. `git log -S"staging_token_shared_secret" -- terraform` returns exactly one commit ever (`168de30`, original creation); there is no `keepers`, no rotation trigger, and no `aws_secretsmanager_secret_rotation` resource anywhere in `terraform/`. Repo absence is weak negative evidence on its own — rotation performed outside terraform would leave no repo trace, which is why Phase 3A left SEC-26 **UNVERIFIED**.
- **Deployed state** (UTC 2026-08-20T00:07:58Z – 00:08:10Z), both secrets, metadata only:
  ```
  intellichoice-staging/learning-api/staging-token-shared-secret
    CreatedDate: 2026-07-24T21:06:18.933Z   LastChangedDate: 2026-07-24T21:06:19.391Z
    LastRotatedDate: null   RotationEnabled: null   RotationRules: null   RotationLambdaARN: null
    VersionIdsToStages: { "terraform-20260724210619234600000003": ["AWSCURRENT"] }
    list-secret-version-ids --include-deprecated -> 1 version
  intellichoice-staging/chat-api/staging-token-shared-secret
    CreatedDate: 2026-07-24T21:06:19.026Z   LastChangedDate: 2026-07-24T21:06:19.411Z
    LastRotatedDate: null   RotationEnabled: null   RotationRules: null   RotationLambdaARN: null
    VersionIdsToStages: { "terraform-20260724210619264500000004": ["AWSCURRENT"] }
    list-secret-version-ids --include-deprecated -> 1 version
  ```
  `LastChangedDate` is 2026-07-24 — **twenty days before the 2026-08-13 exposure**. The
  specified test ("more than one version with a create date after 2026-08-13 is the rotation
  evidence") returns **zero such versions on both secrets**. `LastAccessedDate` is
  **2026-08-18** (learning) and **2026-08-17** (chat), so the un-rotated values are actively read
  by the running tasks, not dormant — LANE-A's SEC-25 read confirms both ARNs are wired into the
  live task definitions' `secrets` blocks. **Contrast:** the two AWS-managed `rds!db-*` secrets
  have `RotationEnabled: true` and were genuinely rotated on **2026-08-14T05:13:21Z** and
  **2026-08-14T00:13:33Z** — the day after the exposure. Rotation demonstrably works in this
  account; its absence here is a gap in this project's provisioning, not an account limit.
- **Evidence**: `aws secretsmanager list-secrets --max-results 100` (Name / Created / LastChanged / LastRotated / LastAccessed / RotationEnabled projection) · `aws secretsmanager describe-secret --secret-id <each>` · `aws secretsmanager list-secret-version-ids --secret-id <each> --include-deprecated`. **No `get-secret-value` was issued anywhere in Phase 3B-1.**
- **Severity**: MEDIUM
- **Phase 3B-2 behavioral verification still needed?**: no — the metadata settles rotation; the separate live-unreachability probe of `/dev/token` belongs to 3B-2 but does not bear on this entry.
- **RESOLVED 2026-08-20 (user-approved remediation)**: D-310's decline was revisited and both secrets were rotated via targeted `terraform apply` at 2026-08-20T03:20:57Z, both services restarted and verified (new secret 200; wrong/no header 404; all tasks post-rotation; full-plan drift check clean). The exposed values were destroyed, not staged. Full record: `REMEDIATION_D310_ROTATION.md`. This entry's deployed-state snapshot above is preserved as the pre-remediation record.
- **Genuine decision required?**: **YES** — whether to revisit D-310's recorded decline, or to schedule rotation at S44's planned deletion of these secrets. Consistent with a recorded decline, this is a **confirmed accepted risk rather than silent drift** — but the exposure is live and `AWSCURRENT`. `docs/INCIDENT_RESPONSE.md` is the relevant runbook. Not decided here.

---

- **Runtime Drift ID**: RD-03
- **Title**: The $20 monthly budget is breached, and $230 of credits hide a ~$250/mo gross run rate from every net-spend control
- **Related claims**: COST-16, COST-15 / **Related decisions**: D-136 and the cost model built on it
- **Intended state**: One `MONTHLY`/`COST` budget at $20 with two notifications (`ACTUAL > 80%`, `FORECASTED > 100%`) warns before spend runs away; `docs/ARCHITECTURE.md`'s D-136 price table describes what the environment costs.
- **Repository state**: `aws_budgets_budget.monthly` at `terraform/modules/observability/main.tf:1-23`, `limit_amount = tostring(var.monthly_budget_usd)` with default 20, exactly the two configured notifications, both emailing `var.notification_email`. `docs/ARCHITECTURE.md:254-283` quotes the D-136 price table (measured at 256 CPU) as current, without the AUD-F-28 resize caveat the terraform carries — and learning-api is live at 512/1024 (COST-29), so those per-task columns understate it by 2×.
- **Deployed state** (UTC 2026-08-20T00:05:19Z – 00:07:43Z):
  ```
  BudgetName: intellichoice-staging-monthly-budget
  BudgetType: COST   TimeUnit: MONTHLY   BudgetLimit: {"Amount":"20.0","Unit":"USD"}
  CalculatedSpend.ActualSpend: {"Amount":"20.939","Unit":"USD"}
  CostTypes: {IncludeCredit: true, IncludeRefund: true, UseAmortized: false}
  LastUpdatedTime: 2026-08-19T15:48:57Z
  Notifications:
    {"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80.0,"NotificationState":"ALARM"}
    {"NotificationType":"FORECASTED","ComparisonOperator":"GREATER_THAN","Threshold":100.0,"NotificationState":"OK"}
  Subscribers (both notifications): EMAIL  k***@gmail.com
  ```
  The budget is at **104.7%** of its limit and its `ACTUAL > 80%` notification is in `ALARM`
  (the `FORECASTED > 100%` notification still reads `OK`, which is internally odd given actual has
  already crossed 100%). Cost Explorer by `RECORD_TYPE` for 2026-08-01 → 2026-08-20:
  `Usage $249.9294156351`, `Tax $1.30`, `Credit $-230.290908019`. Because the repo budget sets
  `IncludeCredit: true` it measures the **post-credit $20.94**; a second, non-repo-managed
  console budget (`"My Monthly Cost Budget"`, $10.00 limit, `CostTypes: null`) measures the
  **gross $251.229** and is also firing. By service, net MTD: `Claude Haiku 4.5 (Amazon Bedrock
  Edition) $19.63850882`, `Tax $1.30`, `Amazon Elastic Container Service $0.0378013638` — no line
  above $0.01 for RDS, ALB, CloudWatch, S3 or `EC2 - Other`, because credits absorb them. The real
  post-credit run rate (~$250/mo incl. NAT $32.9 + Haiku + infra) is **invisible to every
  net-spend control until the credits are exhausted**, at which point the same workload registers
  as ~12× the configured limit.
- **Evidence**: `aws budgets describe-budgets --account-id <acct>` · `aws budgets describe-budget --budget-name intellichoice-staging-monthly-budget` · `aws budgets describe-notifications-for-budget` · `aws budgets describe-subscribers-for-notification` · `aws ce get-cost-and-usage --time-period Start=2026-08-01,End=2026-08-20 --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=RECORD_TYPE` and the same grouped by `Key=SERVICE`.
- **Severity**: MEDIUM
- **Phase 3B-2 behavioral verification still needed?**: no — spend is a Cost Explorer read, already taken; nothing behavioral bears on it.
- **Genuine decision required?**: **YES** — raise, accept, or re-scope the budget, and decide whether a gross (credit-excluding) control is wanted before the credits run out. This is the user's money call. Credit expiry is not exposed by any read-only API, so *when* the step change lands cannot be predicted from this data. Not decided here.

---

- **Runtime Drift ID**: RD-04
- **Title**: LangSmith ingestion is failing at scale right now, and by design nobody is paged
- **Related claims**: COST-27, ARCH-31, ARCH-30 / **Related decisions**: D-242, D-401
- **Intended state**: The `langsmith_ingest_failed` alarm exists so that a broken tracing leg is visible; D-401 deliberately routes it to the quiet `alerts-info` topic rather than the page channel, on the reasoning that it would otherwise "sit in ALARM indefinitely" and desensitise the page mailbox. ARCH-31 recorded that this leg was dark until 2026-08-10 and then started working.
- **Repository state**: filter `for_each = var.log_group_names`, pattern keyed on `$.logger = "langsmith.client"`; alarm threshold 10 over 900 s with `alarm_actions = [aws_sns_topic.alerts_info.arn]` — `terraform/modules/observability/alarms.tf:56-84`, the `alerts_info` action at `:80-81`. The prediction that it would sit in ALARM indefinitely is in the D-401 comment at `terraform/modules/observability/main.tf:75-…`.
- **Deployed state** (UTC 2026-08-20T00:04:59Z – 00:08:12Z): filters present on both app log groups, pattern `{ $.logger = "langsmith.client" }` → `LangSmithIngestFailed`, `value=1`, `default=0.0`, `unit=Count`. Alarms present on both, `Threshold=10.0 GT`, `Period=900`, `EvaluationPeriods=2`, `AlarmActions=[…:intellichoice-staging-alerts-info]`, `OKActions` the same. **14-day Sum: learning-api 2800, chat-api 1441.** Daily series (both services): zero on 08-09 … 08-14, then learning-api 2252 / chat-api 1153 on 08-15, 524 / 239 on 08-16, 0 / 44 on 08-17, 24 / 5 on 08-18. Current state **OK** on both, e.g. chat-api `StateReason`: `"Threshold Crossed: 1 datapoint [10.0 (18/08/26 22:08:00)] was not greater than the threshold (10.0)."` Alarm history shows **10 state transitions each in ~2 days** — learning-api flipped OK→ALARM→OK five times between 2026-08-17T03:02Z and 2026-08-17T23:12Z. So the signal is real and flapping rather than pinned, and every flap lands in `alerts-info`: the informational topic has exactly four member alarms (`langsmith-ingest-failed` ×2, `capacity-above-floor` ×2) against 26 on the page topic, and both topics deliver to the **same single mailbox** `k***@gmail.com`, separable only by topic ARN and mail filter.
- **Evidence**: `aws logs describe-metric-filters --log-group-name /ecs/intellichoice-staging-{learning,chat}-api` · `aws cloudwatch get-metric-statistics --namespace IntelliChoice/intellichoice-staging/<svc> --metric-name LangSmithIngestFailed --period 86400 --statistics Sum` (14 d) · `aws cloudwatch describe-alarm-history --alarm-name intellichoice-staging-<svc>-langsmith-ingest-failed --history-item-type StateUpdate --max-records 10` · `aws sns get-topic-attributes` / `list-subscriptions-by-topic` on both topics.
- **Severity**: MEDIUM
- **Phase 3B-2 behavioral verification still needed?**: no — the failure counts and flap history are CloudWatch reads; identifying the failure *cause* needs log content (403 vs quota vs timeout), which is an ops read, and what LangSmith actually received is external (SEC-23).
- **Genuine decision required?**: **NO** — ops investigation; recorded only. The routing is working as D-401 intended; the ingest failures are the finding.

---

- **Runtime Drift ID**: RD-05
- **Title**: D-419's "NAT absent from the plan entirely" is a misleading sentence — the NAT has existed since 2026-08-07, eleven days before the commit that reported it
- **Related claims**: COST-28, ARCH-29, WORK-08 (D-406 half) / **Related decisions**: D-406, D-419
- **Intended state**: D-406 made the NAT gateway follow its consumers (`private_egress_consumers` → `anytrue` → `nat_gateway_enabled`); `docs/ARCHITECTURE.md` describes the result as "one NAT in one AZ, deliberately". D-419 then reported the NAT as "absent from the plan entirely", which reads as *the NAT does not exist*.
- **Repository state**: `terraform/environments/staging/main.tf:115-117` `private_egress_consumers = {langsmith_tracing = var.langsmith_tracing_enabled, youtube_sync = var.youtube_sync_enabled}`, `:119` `needs_private_egress = anytrue(values(...))`, `:136` `nat_gateway_enabled = local.needs_private_egress`; `aws_nat_gateway.this` with `subnet_id = aws_subnet.public[0].id` at `terraform/modules/vpc/main.tf:85-94`; the `~$33/mo` figure at `modules/vpc/main.tf:170`. Under checked-in defaults (`langsmith_tracing_enabled = true`) the gate evaluates to **count 1**.
- **Deployed state** (UTC 2026-08-20T00:04:13Z – 00:12Z): **exactly one NAT gateway, and it is the only one that has ever existed** — the unfiltered `describe-nat-gateways` returns the same single element, so there is no deleted/failed NAT anywhere in the account's history.
  ```
  NatGatewayId: nat-07ab02d5cd28b6f72   State: available
  SubnetId: subnet-07b390797f61497e8 (public, us-east-1a)   VpcId: vpc-094b422fba4f50e71
  CreateTime: 2026-08-07T04:47:31+00:00   ConnectivityType: public   AvailabilityMode: zonal
  Tags: Name=intellichoice-staging-nat, ManagedBy=terraform, Environment=staging, Project=IntelliChoice
  ```
  The private route table `rtb-0ae773acec1e7ee86` carries an **active `0.0.0.0/0 → nat-07ab02d5cd28b6f72`** route. Dating it against the two commits: D-406 (`15bb6b3`) is 2026-08-18T07:52:56Z and D-419's apply (`2e301d6`) is 2026-08-18T20:32:35Z, so the NAT **predates both by eleven days**. The plan showed no NAT diff because there was nothing to change. Traffic and cost, measured: 26.4 MB out / 12.5 MB in over 14 days (non-zero every day except 2026-08-19, which is 0/0/0), `NatGateway-Hours` 290 hours = **$13.0516 over 12.08 days = $1.080/day ≈ $32.9 per 30.4-day month**, confirming the repo's "~$33/mo" to within rounding — and split by `RECORD_TYPE` into `Usage +$13.05` fully offset by `Credit -$13.05`, i.e. **net $0.00 today**.
- **Evidence**: `aws ec2 describe-nat-gateways` (filtered and unfiltered) · `aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-094b422fba4f50e71` · `git log -1 --format='%H %cI %s' 15bb6b3` and `… 2e301d6` · `aws cloudwatch get-metric-statistics --namespace AWS/NATGateway --metric-name {BytesOutToDestination,BytesInFromDestination,ActiveConnectionCount} --dimensions Name=NatGatewayId,Value=nat-07ab02d5cd28b6f72 --period 86400` · `aws ce get-cost-and-usage … --filter '{"Dimensions":{"Key":"USAGE_TYPE","Values":["NatGateway-Hours","NatGateway-Bytes"]}}'`.
- **Severity**: MEDIUM
- **Phase 3B-2 behavioral verification still needed?**: no — the resource, its route, its traffic and its price are all read; attributing the egress to LangSmith specifically would need VPC Flow Logs, which are not enabled.
- **Genuine decision required?**: **NO** — documentation clarification. `ARCHITECTURE.md`'s "one NAT in one AZ, deliberately" is the accurate text; D-419's sentence described the plan diff, not NAT absence.

---

- **Runtime Drift ID**: RD-06
- **Title**: ARCH-15 refuted — the `CreateDBInstance` rejection cited as proof of Free-Tier restrictions is an engine-version typo
- **Related claims**: ARCH-15 / **Related decisions**: D-122 / AUD-F-28-adjacent (the instance-sizing rationale family)
- **Intended state**: The repo's stated justification for `db.t4g.micro` is that "this AWS account has Free Tier restrictions active (confirmed via a real `CreateDBInstance` rejection during S32/D-084)" — i.e. a hard external constraint forced the class.
- **Repository state**: `terraform/modules/rds-postgres/variables.tf:25-28` (and the matching comment in `terraform/modules/rds-mysql`) carries that assertion as a **self-report only**; Phase 3A classified it UNVERIFIED because it is the repo testifying about itself. `default = "db.t4g.micro"` at `modules/rds-postgres/variables.tf:23-33` and `modules/rds-mysql/variables.tf:23-31`, no environment override.
- **Deployed state** (UTC 2026-08-20T00:10:20Z – 00:12Z): exactly **three** `CreateDBInstance` events in the 90-day CloudTrail window (which reaches back to 2026-05-22, so the S32/D-084 window is fully covered — nothing aged out), all by `jeongsik-staging-admin`:
  | eventTime (UTC) | dBInstanceIdentifier | dBInstanceClass | engine | errorCode | errorMessage |
  |---|---|---|---|---|---|
  | 2026-07-23T01:03:47Z | `intellichoice-staging-mysql` | `db.t4g.micro` | mysql **8.4.3** | **`InvalidParameterCombinationException`** | `Cannot find version 8.4.3 for mysql` |
  | 2026-07-23T01:05:44Z | `intellichoice-staging-postgres` | `db.t4g.micro` | postgres 16.4 | none | — (succeeded) |
  | 2026-07-23T01:05:45Z | `intellichoice-staging-mysql` | `db.t4g.micro` | mysql 8.4.10 | none | — (succeeded) |
  The single rejection was requested **already at `db.t4g.micro`** and was retried as 8.4.10 two minutes later and succeeded — it has nothing to do with instance size, Free Tier, or a `db.t4g.small` request. Independently, `freetier get-free-tier-usage` returns **16 rows, every one `freeTierType: "Always Free"`**, with **no `"12 Month Free"` row of any kind** — notably no RDS `db.t*.micro` 750-hour row. Paid RDS, NAT and Fargate resources all provisioned successfully, which rules out an account-level Free-Tier-plan restriction.
- **Evidence**: `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=CreateDBInstance --start-time 2026-05-22T00:10:23Z --max-results 50` then the full `CloudTrailEvent` JSON of each read for `errorCode` / `errorMessage` / `requestParameters` · `aws freetier get-free-tier-usage --region us-east-1` · `aws ce get-cost-and-usage … --filter '{"Dimensions":{"Key":"SERVICE","Values":["EC2 - Other"]}}'`.
- **Severity**: MEDIUM
- **Phase 3B-2 behavioral verification still needed?**: no — the claim named its own evidence, the record was retrieved in full, and the claim is falsified on it. ARCH-15 does not close as "unfalsifiable read-only".
- **Genuine decision required?**: **NO** — the comment's causal statement is a misattribution and the fix is an edit. The `db.t4g.micro` **choice** itself remains sound; only the stated justification is wrong. This **WEAKENS** the Phase-2/3A ARCH-15 claim.

---

- **Runtime Drift ID**: RD-07
- **Title**: Zero product-KPI alarms are deployed while both KPI metrics carry live data — a floor would be meaningful today
- **Related claims**: COST-21 (and P1-10) / **Related decisions**: D-377 P1-10
- **Intended state**: `sessions_completed_floor` is the one product-KPI alarm in the design, and staging deliberately sets its floor to 0, which count-gates the resource out of existence. P1-10 recorded the resulting blind spot as an open item.
- **Repository state**: `terraform/modules/observability/app_events.tf:130-131` `count = var.daily_completed_sessions_floor > 0 ? 1 : 0`; `terraform/environments/staging/main.tf:787` sets it to `0` explicitly. `qa_answers_total` has no alarm resource anywhere. The double guard means the alarm cannot exist in staging.
- **Deployed state** (UTC 2026-08-20T00:04:30Z): **product-KPI alarm count deployed = 0**, proven three independent ways — `describe-alarms --alarm-name-prefix intellichoice-staging-learning-sessions-completed-floor` → `{"MetricAlarms":0,"CompositeAlarms":0}`; a name/metric regex over the unfiltered 34-alarm dump whose only hit is `intellichoice-staging-job-session-consolidate-heartbeat` (matched on the word "session" in a *job* name, metric `JobCompletions`); and all four `describe-alarms-for-metric` calls across both namespaces for `learning_sessions_completed_total` and `qa_answers_total` → `{"MetricAlarms":0}`. Meanwhile **both KPI metrics exist and carry data**: `learning_sessions_completed_total` 11 datapoints / Sum 8 over 30 d, and `qa_answers_total{result=grounded}` 9 datapoints / Sum 409 over 30 d. The 34 deployed alarms break down as ALB 6, ECS/ContainerInsights 4, RDS 6, metric-math 2, custom-namespace app-plumbing 12, pipeline-ops 4 — **none of them a product KPI.** More broadly, 63 custom app metrics carry data and only 12 have alarms.
- **Evidence**: `aws cloudwatch describe-alarms --max-records 100` (single page, `MetricAlarms: 34`, `CompositeAlarms: 0`, no `NextToken`) · `aws cloudwatch describe-alarms --alarm-name-prefix intellichoice-staging-learning-sessions-completed-floor` · `aws cloudwatch describe-alarms-for-metric --namespace IntelliChoice/intellichoice-staging/{learning-api,chat-api} --metric-name {learning_sessions_completed_total,qa_answers_total}` · `aws cloudwatch list-metrics --namespace IntelliChoice/intellichoice-staging/{learning-api,chat-api,pipeline}` · `aws cloudwatch get-metric-statistics` on both KPI metrics (30 d).
- **Severity**: MEDIUM
- **Phase 3B-2 behavioral verification still needed?**: no — the negative is authoritative from the unfiltered enumeration, and the KPI series are already measured.
- **Genuine decision required?**: **NO** for this entry, which **strengthens the existing decision-required entry** rather than opening a new one: the open question stays "raise `daily_completed_sessions_floor`, or record the disabled state as the answer". Runtime evidence now says a floor would be meaningful today, because the metrics it would read are live.

---

- **Runtime Drift ID**: RD-08
- **Title**: The §7-R9 checkpoint-repair tripwire is charted but never alarmed — the metric exists with data in the deployed account and no alarm references it
- **Related claims**: SEC-10 / **Related decisions**: D-148 §7-R9
- **Intended state**: §7-R9 treats checkpoint repairs as a tripwire — a rising repair count is supposed to be noticed.
- **Repository state**: `learning_checkpoint_repairs_total` is instrumented and appears in dashboard widgets; no `aws_cloudwatch_metric_alarm` block references it. The eight `alarms.tf` blocks (`terraform/modules/observability/alarms.tf:29-238`) cover Bedrock, RDS, ECS memory and LangSmith — not this.
- **Deployed state** (UTC 2026-08-20T00:04:06Z): a regex over the full 34-alarm dump for `checkpoint|repair` returns `{"checkpoint_repair_alarms": []}` — **no deployed alarm references `learning_checkpoint_repairs_total` or `checkpoint_repair`.** The metric itself **does** exist with data in the deployed namespace (it is one of the 35 `IntelliChoice/intellichoice-staging/learning-api` metrics carrying data in the trailing window), and it is charted on the live `intellichoice-staging-overview` dashboard (19 widgets, LastModified 2026-08-10T05:41:04Z). So this is an instrumented-but-unalarmed signal, not a missing metric. Same pass confirmed SEC-10's positive half: all eight `alarms.tf` blocks exist at ×2 each = 16 instances, every threshold, period, evaluation-period and treat-missing-data value matching config, including `ecs_memory` at **716.0** MiB and the per-engine `rds_connections` split (postgres 80.0, mysql 40.0).
- **Evidence**: `aws cloudwatch describe-alarms --max-records 100` filtered for `checkpoint|repair` · `aws cloudwatch list-metrics --namespace IntelliChoice/intellichoice-staging/learning-api` · `aws cloudwatch list-dashboards` + `aws cloudwatch get-dashboard --dashboard-name intellichoice-staging-overview`.
- **Severity**: MEDIUM
- **Phase 3B-2 behavioral verification still needed?**: no — existence and non-existence are both settled at the control plane.
- **Genuine decision required?**: **NO** — this **strengthens the existing Phase 3A entry** by moving SEC-10 from file state to runtime-proven; whether to add an alarm is already tracked there.

---

- **Runtime Drift ID**: RD-09
- **Title**: RDS operational posture — 1-day backup retention, deletion protection off, single-AZ on both instances, with no document recording it as a decision
- **Related claims**: new observation (surfaced by ARCH-14's `describe-db-instances` call) / **Related decisions**: none recorded
- **Intended state**: Not recorded anywhere. `multi_az` defaults to `false` in the modules and no environment override exists, so single-AZ is intentional-by-default; but no document states the 1-day backup window or the disabled deletion protection as a choice, with its consequence.
- **Repository state**: `modules/rds-mysql/variables.tf` ~`:38` `multi_az` default `false`; `allocated_storage_gb` default 20 in both modules; no `instance_class` override at `terraform/environments/staging/main.tf:248` or `:257`. No variable or comment anywhere records backup retention or deletion protection as a deliberate staging posture.
- **Deployed state** (UTC 2026-08-20T00:04Z), identical on both instances:
  | field | `intellichoice-staging-postgres` | `intellichoice-staging-mysql` |
  |---|---|---|
  | `BackupRetentionPeriod` | **1** | **1** |
  | `DeletionProtection` | **`false`** | **`false`** |
  | `MultiAZ` | `false` | `false` |
  | `AvailabilityZone` | `us-east-1a` | `us-east-1a` |
  | `DBInstanceClass` | `db.t4g.micro` | `db.t4g.micro` |
  | `Engine` / `EngineVersion` | `postgres` / `16.4` | `mysql` / `8.4.10` |
  | `StorageEncrypted` | `true` | `true` |
  | `PubliclyAccessible` | `false` | `false` |
  | `DBParameterGroups` | `default.postgres16` | `default.mysql8.4` |
  | `PerformanceInsightsEnabled` | `false` | `false` |
  Both are in the **same AZ**, so one AZ loss takes out both databases, and point-in-time recovery reaches back **one day**. Both parameter groups are AWS **defaults** — no custom group is attached to either instance, so any parameter-level tuning claim cannot be true today. Acceptable for staging on its face; the material point is that **this is the environment the §2.6 gate criteria were measured on**.
- **Evidence**: `aws rds describe-db-instances` with the full field projection (id, class, engine, version, multiAZ, storage, storageType, dbName, public, backupRetention, status, created, az, parameter groups, encrypted, deletionProtection, perfInsights).
- **Severity**: MEDIUM
- **Phase 3B-2 behavioral verification still needed?**: no — a restore drill would be a real exercise, not a browser walk, and is out of this phase's scope entirely.
- **Genuine decision required?**: **YES** — a launch-posture call: what backup retention, deletion protection and AZ posture the gate criteria are allowed to have been measured on, and what production requires. Named, not answered.

### LOW

- **Runtime Drift ID**: RD-10
- **Title**: CloudWatch is past the 10-alarm always-free limit — 24 of 34 alarms are billable and the cost model does not mention alarm billing
- **Related claims**: COST-25, COST-15 / **Related decisions**: D-401
- **Intended state**: The cost model enumerates what the environment costs. Alarm billing is not in it.
- **Repository state**: 15 `aws_cloudwatch_metric_alarm` resource blocks — `terraform/modules/observability/main.tf:132,208,231` (3), `alarms.tf:29,56,87,115,136,163,187,213` (8), `app_events.tf:45,96,130,202` (4) — which expand to **30** instances at staging cardinality (services 2, log groups 2, capacity floors 2, database instances 2, nightly job events 4, `daily_completed_sessions_floor` 0). No cost-model document mentions a per-alarm charge.
- **Deployed state** (UTC 2026-08-20T00:04:06Z / 00:13Z): **34 `MetricAlarms`, 0 `CompositeAlarms`** = 30 observability-module instances + 4 created by Application Auto Scaling from the step-scaling policies. Per-name delta against config is **0** — not one configured instance is missing and not one deployed alarm is unaccounted for. Free-tier usage on the same account: `AmazonCloudWatch CW:AlarmMonitorUsage` **Actual 10.0, Forecast 16.32, Limit 10.0 — at limit and forecast to exceed** (and `CW:MetricMonitorUsage` likewise 10.0 / 16.32 / 10.0). So 24 of the 34 alarms are billable at ~$0.10/alarm/month ≈ **$2.40/mo**, forecast **16.3 alarm-months** this cycle. Also on the same read: `AWS X-Ray XRay-TracesStored` 91,077 actual / 148,599 forecast against a 100,000 limit (91% used, forecast to exceed) — a small forthcoming cost consistent with the OTel sidecar actively exporting.
- **Evidence**: `aws cloudwatch describe-alarms --max-records 100` (single page) · `aws cloudwatch describe-alarms --alarm-types CompositeAlarm` · `aws application-autoscaling describe-scaling-policies --service-namespace ecs` · `aws freetier get-free-tier-usage --region us-east-1`.
- **Severity**: LOW
- **Phase 3B-2 behavioral verification still needed?**: no — counts and free-tier usage are direct reads.
- **Genuine decision required?**: **NO** — a cost-model omission; the charge is ~$2.40/mo and the alarm inventory itself matches config exactly.

---

- **Runtime Drift ID**: RD-11
- **Title**: Both services run one task-definition revision behind their family's latest — revision-number drift, not image drift
- **Related claims**: ARCH-34, WORK-06 / **Related decisions**: D-418, D-137
- **Intended state**: `make image-check` exists so an operator can confirm each service's running task definition is its family's latest revision; D-137 recorded the family-resolution trap that makes an unsuffixed family reference resolve to LATEST rather than to what is running.
- **Repository state**: `make image-check` at `Makefile:292-294` invoking `scripts/check_deployed_image_consistency.py` — **operator-invoked only, wired into neither CI nor `deploy-staging.yml`**. `adopt_deployed_image` default `true` (`terraform/environments/staging/variables.tf:201-202`) consumed by the `for_each` guard at `terraform/environments/staging/main.tf:12`; image expression at `main.tf:45`/`:49` with `learning_api_image_tag` / `chat_api_image_tag` both defaulting to `"unset"` (`variables.tf:32-39`). `ignore_changes = [task_definition]` on the services is what prevents adoption.
- **Deployed state** (UTC 2026-08-20T00:04Z – 00:06Z):
  | family | family LATEST | service's revision | latest `registeredAt` | service revision `registeredAt` |
  |---|---|---|---|---|
  | `intellichoice-staging-learning-api` | **151** | **150** | 2026-08-18T20:20:41.514Z | 2026-08-18T18:46:27.648Z |
  | `intellichoice-staging-chat-api` | **149** | **148** | 2026-08-18T20:20:41.514Z | 2026-08-18T18:49:32.753Z |
  | `intellichoice-staging-ops-task` | **144** | (no service) | 2026-08-18T20:20:41.511Z | — |
  All three families' latest revisions were registered **within 3 milliseconds of each other** at 2026-08-18T20:20:41Z — the signature of a single `terraform apply`, ~1.5 h *after* the two service deployments were created. A normalised diff (ignoring `revision`/`registeredAt`/`taskDefinitionArn`/`registeredBy`) shows `chat-api:148` vs `:149` **byte-identical**, and `learning-api:150` vs `:151` differing **only** in the ordering of the `compatibilities` array (`["MANAGED_INSTANCES","FARGATE"]` vs `["FARGATE","MANAGED_INSTANCES"]`), a server-side serialisation artifact. Image identity is unaffected: `gha-44a12dfc9549` is live on both services **by tag and by digest** (`sha256:eb0b1823…b7d21c` on learning-api's two tasks, `sha256:06965774…90eba0` on chat-api's), one `PRIMARY` deployment per service, both `rolloutState: COMPLETED`. So the D-137 family-resolution trap is **live-armed but harmless today** — identical content on both sides.
- **Evidence**: `aws ecs describe-services --cluster intellichoice-staging --services … --query 'services[].[serviceName,taskDefinition]'` · `aws ecs list-task-definitions --family-prefix <each> --sort DESC --max-items 5` · `aws ecs describe-task-definition --task-definition <family>` (resolves to LATEST) vs `<family>:<revision>` · normalised local diff of the two JSON documents · `aws ecr describe-images` on both repositories · `aws ecs describe-tasks … --query 'tasks[].containers[].[name,lastStatus,image,imageDigest]'`.
- **Severity**: LOW
- **Phase 3B-2 behavioral verification still needed?**: no — the tfvars-staleness half is not answerable from AWS at all (with `adopt_deployed_image = true` the `var.*_image_tag` pin is bypassed, so its staleness is unobservable from the control plane, and `terraform.tfvars` is out of scope), and the revision/image question is fully answered.
- **Genuine decision required?**: **NO** — `make image-check` is the existing operator-invoked control; a tool comparing revision numbers reports drift, a tool comparing images reports none, and that distinction is the finding.

---

- **Runtime Drift ID**: RD-12
- **Title**: The documented `learning.` / `chat.intellichoice.org` entry points do not exist live — CloudFront carries no custom aliases
- **Related claims**: ARCH-28 (ingress half), documented-hostname claims in `CLAUDE.md` / SPEC / **Related decisions**: C3 / S48 (DNS at integration time)
- **Intended state**: `learning.intellichoice.org` and `chat.intellichoice.org` are the product's entry points — but DNS records are C3/S48 scope, added by the org at integration time, so their absence today is expected rather than a defect.
- **Repository state**: `terraform/modules/cloudfront-spa-api/main.tf:128` `cloudfront_default_certificate = true`, `:53` `price_class = var.price_class`; no alias/ACM-certificate configuration anywhere, which is self-consistent — a custom alias would require an ACM certificate. So the deployed state matches the repo; the gap is between the repo and the documented hostnames.
- **Deployed state** (UTC 2026-08-20T00:05Z): **two** distributions, both `Enabled: true`, `Status: Deployed`, `PriceClass: PriceClass_100`, `LastModifiedTime: 2026-07-23T06:14:55Z`, `ViewerCertificate.CloudFrontDefaultCertificate: true`, **`Aliases: null`**, `DefaultRootObject: null`:
  | id | domain | comment | origins |
  |---|---|---|---|
  | `E371R2SNCXJW2C` | `d35dfnjzmgrm01.cloudfront.net` | `intellichoice-staging-learning` | `learning-s3` (OAC `E27N425U9TKYC2`) + `learning-alb` → `intellichoice-staging-alb-1331167894.us-east-1.elb.amazonaws.com` |
  | `E3EP2M0Q2XRXWZ` | `d222glidpp4azv.cloudfront.net` | `intellichoice-staging-chat` | `chat-s3` (OAC `EKKO5P5BHJ242`) + `chat-alb` → same ALB |
  The deployed entry points are therefore the `*.cloudfront.net` domains. **Companion fact for whoever runs 3B-2:** the ALB's security group `sg-04a0e7a83052aeb8c` admits tcp/80 **only** from the managed prefix list `pl-3b927c52` = `com.amazonaws.global.cloudfront.origin-facing` (owner `AWS`) — there is no `0.0.0.0/0` on port 80 anywhere, and the ALB has **no port-443/HTTPS listener** (one HTTP:80 listener, default action `fixed-response 404`, matching `terraform/modules/alb/main.tf:51-58`). **3B-2 must probe through CloudFront; a direct-to-ALB timeout is by design and must not be read as an outage.**
- **Evidence**: `aws cloudfront list-distributions` · `aws elbv2 describe-load-balancers` / `describe-listeners` / `describe-target-groups` / `describe-target-health` · `aws ec2 describe-security-groups --filters Name=vpc-id,Values=vpc-094b422fba4f50e71` · `aws ec2 describe-managed-prefix-lists --query 'PrefixLists[?PrefixListId==`pl-3b927c52`]'`.
- **Severity**: LOW
- **Phase 3B-2 behavioral verification still needed?**: yes, indirectly — 3B-2's probes must target the two `*.cloudfront.net` domains; this entry exists so that the hostname substitution and the expected direct-ALB timeout are recorded before those walks start.
- **Genuine decision required?**: **NO** — expected pre-integration state, recorded as informative rather than as a defect.

## 3. Index tables

### 3.1 By severity

| Severity | Count | Entries |
|---|---|---|
| **HIGH** | **1** | RD-01 |
| **MEDIUM** | **8** | RD-02, RD-03, RD-04, RD-05, RD-06, RD-07, RD-08, RD-09 |
| **LOW** | **3** | RD-10, RD-11, RD-12 |
| **Total** | **12** | RD-01 … RD-12 |

### 3.2 Genuine decisions required

Three of the twelve need a judgement rather than an edit or a mechanical fix. All three plausibly
belong to the **user** — this is a solo-maintained project and each is a money, security-posture or
launch-posture call, not an engineering detail a session can settle on its own.

| Entry | The decision, named | Plausible owner |
|---|---|---|
| **RD-02** | Secret rotation: revisit D-310's recorded decline, or schedule rotation at S44's planned deletion — with the exposed values live and `AWSCURRENT` six days on | user |
| **RD-03** | Budget: raise, accept, or re-scope the $20 monthly limit, and decide whether a gross (credit-excluding) control is wanted before ~$230 of credits are exhausted | user |
| **RD-09** | RDS launch posture: what backup retention, deletion protection and AZ posture the §2.6 gate criteria are allowed to have been measured on, and what production requires | user |

The other nine are **NO**: RD-01 is a one-line mechanical fix; RD-05 and RD-06 are documentation
corrections; RD-04 is an ops investigation; RD-07 and RD-08 strengthen decision-required entries
that already exist elsewhere rather than opening new ones; RD-10, RD-11 and RD-12 are cost-model,
tooling and pre-integration notes.

### 3.3 What Phase 3B-2 must still verify

Six queue items were routed out of 3B-1 as behavioral — none of them answerable from the AWS
control plane. Lines are the runtime question as `targets_3b1.md` states it.

| Claim | What 3B-2 must do |
|---|---|
| **REQ-46** | Measure access-hint recall on current staging traffic rather than quoting D-371's number — needs a labelled query set run against the deployed RAG path. |
| **TEST-21** | Re-run the test suites and compare current counts against the quoted ones — a local `pytest`/`make test` execution; 3A never ran a test and 3A.5 ran targeted batches only. |
| **TEST-28** | Same lane as TEST-21: re-run the suites and compare counts against the recorded ones; execute the two together. |
| **WORK-05** | Re-run the quoted counts on current HEAD — local greps/counts, no AWS surface. |
| **WORK-13** | Confirm the `journey-student.spec.ts` isolation defect is behaviourally resolved when the learning e2e walks run in combination against staging — a Playwright run. |
| **WORK-29** | Produce a validation run and measure the reject threshold against the recorded one. **Cost flag:** any arm that invokes generation is a **paid** run needing explicit user approval and exported model ids — never an audit-phase default. |

Two standing hazards for that phase, both already established above: never run `make test` and
Playwright concurrently (they share the dev Postgres), and probe through CloudFront rather than the
ALB (RD-12).

Also routed out of 3B-1 and **not** 3B-2's work: 3 external items (ARCH-33 GitHub settings, SEC-23
LangSmith account retention, WORK-44 PR backlog) and 5 forbidden (SEC-27, TEST-04
branch-protection, INT-29 deployed knowledge store, WORK-03 staging schema, WORK-20 — each needs
secret values, database content, or GitHub admin). Of 56 queue items, 42 were inspected in 3B-1
with zero `ACCESS_UNAVAILABLE`. No item was deferred by D-152: integration items were never queued
to 3B-1.

### 3.4 Earlier-phase claims settled by runtime evidence

**Strengthened / confirmed at runtime.**

- **WORK-08** — **D-401 is APPLIED, not merely committed**: the `alerts-info` topic exists in AWS
  with a confirmed email subscription, the four-alarm informational routing is live, and the
  2026-08-18T20:20:41Z three-family task-definition registration burst is positive evidence that a
  `terraform apply` ran that day. `PROGRESS.md:155-156`'s "unapplied" is **REFUTED** — ROADMAP was
  right.
- **COST-25** — deployed module alarm instances **30** == configured **30**, per-name delta **0**.
- **COST-23 / COST-26** — both email subscriptions **CONFIRMED**, zero `PendingConfirmation`
  anywhere in the account; the audit-era PendingConfirmation observation is resolved.
- **COST-21, SEC-10** — runtime-proven (see RD-07, RD-08).
- **ARCH-10, ARCH-11, ARCH-12, ARCH-13, ARCH-14, ARCH-22, ARCH-30, ARCH-35, SEC-25, COST-29,
  COST-17, COST-19 (configuration half)** — all confirmed against the deployed state.
- **SEC-16** — `IsLogging: true`, and delivery is **90 s fresh**
  (`LatestDeliveryAttemptSucceeded: 2026-08-20T00:06:12Z`), not merely configured.
- **TEST-09** — GuardDuty is **genuinely absent** (`{"DetectorIds": []}`), an account property and
  not merely an absence from terraform; WAF empty in both scopes.
- **ARCH-02** — no AWS Organizations structure exists
  (`AWSOrganizationsNotInUseException`, the informative branch rather than a permissions wall).
- **ARCH-04, ARCH-07, WORK-35 (schedule half)** — schedules exact, including the per-job retry
  asymmetry (`memory-consolidate = 0`).
- **NAT ≈ $33/mo** — the repo's figure confirmed by Cost Explorer measurement (~$32.9/mo gross).

**Weakened / refuted.**

- **ARCH-15** — the Free-Tier justification is refuted (RD-06).
- **D-419's NAT sentence** — "absent from the plan entirely" is misleading; the NAT predated the
  commit by eleven days (RD-05).
- **`PROGRESS.md`'s "D-401/D-406 unapplied"** — refuted by live resources.
- **COST-18's "filters correct, so the metric will flow"** expectation — refuted: the filters are
  exactly as written and the metric has never published (RD-01).
- **The Phase 3A comfort that the dead-man's-switch posture was "resolved at config level"** — the
  config **is** exact, and the instrument still cannot work (RD-01).

Two further claims moved to partial rather than either pole: **REQ-50(b)** (100-concurrent capacity
was never demonstrated live — 30-day peak ≈ 3 req/s, busiest minute 51 requests, so capacity
remains a load-test-era extrapolation) and **REQ-18** (schema-invalid capture is absent from the
deployed stack **and** from the repo, so deployed matches repo; the intent gap is the existing
Phase 3A entry's subject). Neither opens a new runtime drift entry.
