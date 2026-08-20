> **ARCHIVED 2026-08-20.** Point-in-time audit evidence (reconciliation, 2026-08-19/20) — **do not treat as current state.**
> **Current state:** `docs/PROJECT_STATE.md`
> **Reason:** Phase 3B-1 deployed-infrastructure evidence — the verbatim read-only AWS reads behind the drift register. **Superseded by:** the 166-entry register at `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`.

# DEPLOYED_INFRA_STATE_EVIDENCE.md — Phase 3B-1 deployed-infrastructure verification

**Observation window:** 2026-08-19T22:00Z – 2026-08-20T00:30Z.
**Environment observed:** AWS account `3205…`, region `us-east-1`, profile `jeongsik-staging-admin`
(an IAM **user** with static keys, `arn:aws:iam::3205…:user/jeongsik-staging-admin` — not an
`aws login` session).

**Method and constraints.** Every observation in this file came from a `list-*` / `describe-*` /
`get-*` control-plane call. **Strictly read-only:** no mutating verb of any kind, no
`secretsmanager get-secret-value` (secret *metadata* and ARNs only), no log **content** read
(`get-log-events` / `filter-log-events` / Logs Insights were not run in any lane), no
`terraform plan` / `apply` / `init`, no `.env` or `terraform.tfvars` read. **Zero `AccessDenied`
across all three lanes** — every command in scope returned data. Two non-permission exceptions were
encountered and are themselves answers, not failures: `AWSOrganizationsNotInUseException`
(ARCH-02) and `InsightNotEnabledException` (SEC-16). Email local-parts are masked (`k***@gmail.com`).

**The governing rule of this phase:** terraform configuration and AWS state were kept as **two
separate evidence sources**, never merged. `LOCAL_EXECUTION_FINDINGS.md` F-03 is why — the
repository's own comment at `terraform/environments/staging/main.tf:547-552` records a config change
(D-344, `autoscaling_max_capacity = 1`) that was written and never applied. Each block below
therefore states the repository-configured state and the observed deployed state as independent
lines, and the classification is the *relation between them*. Where the two agree, that agreement is
an observation, not an assumption.

**Companion documents.** The drift narrative — what each divergence means, its severity, and whether
it needs a judgement — lives in the companion register (`DEPLOYED_INFRA_DRIFT_REGISTER`, entries
RD-01 … RD-12). This file carries evidence and cross-references only; it makes no recommendations.

---

## 1. Coverage

The Phase 3B-1 queue held **56 items**. Their disposition:

| Disposition | Count | Items |
|---|---|---|
| **Inspected in 3B-1** | **42** | LANE-A 15, LANE-B 16, LANE-C 11 (see §2) |
| Deferred to Phase 3B-2 (behavioural) | 6 | REQ-46, TEST-21, TEST-28, WORK-05, WORK-13, WORK-29 |
| External (outside AWS) | 3 | ARCH-33, SEC-23, WORK-44 |
| Forbidden read-only | 5 | SEC-27, TEST-04, INT-29, WORK-03, WORK-20 |
| **ACCESS_UNAVAILABLE** | **0** | — |
| **DEFERRED_BY_D152** | **0** | integration items were never queued to 3B-1 |

Lane ownership of the 42 (no claim has two owners):

- **LANE-A — compute / deploy (15):** ARCH-02, ARCH-03, ARCH-08, ARCH-10, ARCH-11, ARCH-12,
  ARCH-13, ARCH-14, ARCH-22, ARCH-30 *(sidecar half; filter half executed by LANE-B)*, ARCH-34,
  ARCH-35, SEC-25, COST-29, WORK-06.
- **LANE-B — observability / alerting (16):** COST-15, COST-16, COST-17, COST-18, COST-19,
  COST-21, COST-23, COST-24, COST-25, COST-26, COST-27, REQ-18, REQ-50, SEC-10, WORK-02,
  WORK-08 *(D-401/SNS half)*.
- **LANE-C — networking / scheduling / security metadata (11):** ARCH-04, ARCH-07, ARCH-15,
  ARCH-28, ARCH-29, COST-28, SEC-16, SEC-26, TEST-09, WORK-23, WORK-35 *(schedule half)*.

15 + 16 + 11 = 42; 42 + 6 + 3 + 5 = 56.

---

## 2. Per-claim evidence blocks

42 blocks, grouped by family, sorted by ID.

### 2.1 ARCH family (17)

#### ARCH-02 — exactly one deployed environment; any Organizations structure?

- **Claim ID**: ARCH-02
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (config half)
- **Intended state**: one staging environment only, with no production twin and no AWS Organizations structure implying one.
- **Repository-configured state**: `terraform/environments/` has exactly one child, `staging/`; no `production/` directory and no `aws_organizations_*` resource anywhere.
- **Observed deployed state**: account `3205…`, user `jeongsik-staging-admin`. **One** ECS cluster (`intellichoice-staging`); **two** RDS instances (`intellichoice-staging-mysql` mysql, `intellichoice-staging-postgres` postgres); **one** ELBv2 (`intellichoice-staging-alb`); 4 S3 buckets, all `intellichoice-staging-*` / `intellichoice-terraform-state-*`; **no `production`-prefixed resource anywhere**. Two VPCs: `vpc-094b422fba4f50e71` `10.0.0.0/16` Name=`intellichoice-staging-vpc`, plus the account's untouched **default** VPC `vpc-0a540ff27b5b06b31` `172.31.0.0/16` (`IsDefault: true`, untagged). Organizations, verbatim: `An error occurred (AWSOrganizationsNotInUseException) when calling the DescribeOrganization operation: Your account is not a member of an organization.` — the informative branch, **not** `AccessDenied`. Corroborating: `cloudtrail describe-trails` → `IsOrganizationTrail: false`.
- **Evidence source**: `aws sts get-caller-identity` / `aws ecs list-clusters` / `aws rds describe-db-instances --query 'DBInstances[].[DBInstanceIdentifier,Engine]'` / `aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerName'` / `aws ec2 describe-vpcs` / `aws s3api list-buckets --query 'Buckets[].Name'` / `aws organizations describe-organization`
- **Observed at**: 2026-08-20T00:05Z (LANE-A; org half corroborated by LANE-C at 00:07:28Z)
- **Limitations**: enumerates `us-east-1` only — a resource in another region would not appear. Says nothing about a prod-like deployment in a *different* AWS account (none is reachable from these credentials). The default VPC is an artifact of account creation, not a second environment.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-03 — any deployed identity provider; is the dev-token env contract still on the task definitions?

- **Claim ID**: ARCH-03
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (repo half)
- **Intended state**: no independent identity provider is deployed; `/dev/token` remains the only token-issuing route.
- **Repository-configured state**: the only OIDC provider in terraform is the GitHub Actions deploy provider (`terraform/modules/iam/main.tf:129-190`); zero auth-provider hits in `apps/*/src` and `packages/*/src`.
- **Observed deployed state**: `{"UserPools": []}` — **zero** Cognito user pools. IAM OIDC providers: **exactly one**, `arn:aws:iam::3205…:oidc-provider/token.actions.githubusercontent.com`. `{"SAMLProviderList": []}` — zero SAML providers. Dev-token env contract still present on both deployed task definitions: `LEARNING_DEV_TOKEN_ENDPOINT_ENABLED = "false"`, `CHAT_DEV_TOKEN_ENDPOINT_ENABLED = "false"`.
- **Evidence source**: `aws cognito-idp list-user-pools --max-results 60` / `aws iam list-open-id-connect-providers` / `aws iam list-saml-providers` / `aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api:150 --query 'taskDefinition.containerDefinitions[0].{env:environment,secrets:secrets}'`
- **Observed at**: 2026-08-20T00:05Z (LANE-A)
- **Limitations**: does not test whether the deployed apps actually *issue* dev tokens — that is an HTTP probe (3B-2). Only the IAM and Cognito IdP surfaces were checked; an IdP embedded in application code would not appear here.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-04 — four ENABLED Scheduler schedules with exact crons in UTC, plus a DISABLED fifth

- **Claim ID**: ARCH-04
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: `session-consolidate` 18:00, `chat-purge` 18:10, `memory-consolidate` Sun 18:30, `retention-purge` 18:50 — all ENABLED, all UTC; `youtube-sync` DISABLED.
- **Repository-configured state**: five jobs in `locals.jobs`, four `enabled = true`; `schedule_expression_timezone = "UTC"` hardcoded at `terraform/modules/scheduled-jobs/main.tf:196`; `group_name = "default"` at `:187`; `maximum_event_age_in_seconds = 3600` at `:231`.
- **Observed deployed state**: one schedule group (`default`, `ACTIVE`) and **exactly five schedules — no more, no fewer**. `…-session-consolidate` ENABLED `cron(0 18 * * ? *)` UTC retries 2, created 2026-08-16T04:10:34Z; `…-chat-purge` ENABLED `cron(10 18 * * ? *)` UTC retries 2, created 2026-07-27T02:48:30Z; `…-memory-consolidate` ENABLED `cron(30 18 ? * SUN *)` UTC retries **0**, created 2026-07-27T02:48:30Z; `…-retention-purge` ENABLED `cron(50 18 * * ? *)` UTC retries 2, created 2026-07-29T14:41:04Z; `…-youtube-sync` **DISABLED** `cron(0 19 ? * SUN *)` UTC retries 2, created 2026-07-27T02:48:38Z, **modified 2026-07-27T03:02:22Z**. All five target cluster `intellichoice-staging` via role `intellichoice-staging-scheduler`, family `intellichoice-staging-ops-task`, `LaunchType: FARGATE`, `TaskCount: 1`, `FlexibleTimeWindow.Mode: OFF`, `MaximumEventAgeInSeconds: 3600`, both private subnets, `AssignPublicIp: DISABLED`. `memory-consolidate`'s live `MaximumRetryAttempts: 0` confirms the per-run paid-API budget guard is applied, not merely written. Only `youtube-sync` has `LastModificationDate ≠ CreationDate` — consistent with created-enabled then switched off ~14 minutes later; nothing else has been hand-edited in the console.
- **Evidence source**: `aws scheduler list-schedule-groups` / `aws scheduler list-schedules` / `aws scheduler get-schedule --group-name default --name intellichoice-staging-<job>` (×5)
- **Observed at**: 2026-08-20T00:05:5xZ (LANE-C)
- **Limitations**: `get-schedule` reports **declared** state, not execution history. Whether these schedules fired is WORK-35 / COST-18 / RD-01, and the heartbeat instrument that was supposed to answer it cannot (see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-01).
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-07 — is `youtube-sync` DISABLED, and is `webcontent-sync` absent entirely?

- **Claim ID**: ARCH-07
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: `youtube-sync` exists but is off; `webcontent-sync` was never created.
- **Repository-configured state**: `cron(0 19 ? * SUN *)`, `enabled = var.youtube_sync_enabled` (`modules/scheduled-jobs/main.tf:125`), default `false` in both module (`modules/scheduled-jobs/variables.tf:63`) and environment (`environments/staging/variables.tf:169`); `webcontent-sync` deliberately never defined — the only mention in `terraform/` is a prose comment at `modules/scheduled-jobs/main.tf:21`.
- **Observed deployed state**: the schedule **exists** and its `State` is **`DISABLED`** — not a `ResourceNotFoundException`; the queue asked which, and this is the "exists but off" answer. No schedule matching `webcontent` exists; the five names under ARCH-04 are the complete set. **This closes the unread-`terraform.tfvars` question for both NAT flags by observation rather than by file read**: `youtube-sync` DISABLED ⇒ applied `youtube_sync_enabled = false`; a live NAT plus `nat_gateway_enabled = anytrue({langsmith_tracing, youtube_sync})` then forces `langsmith_tracing_enabled = true`. The applied values are the checked-in defaults, and **LangSmith is the NAT's sole consumer today**.
- **Evidence source**: `aws scheduler get-schedule --group-name default --name intellichoice-staging-youtube-sync` / `aws scheduler list-schedules`
- **Observed at**: 2026-08-20T00:05:5xZ (LANE-C)
- **Limitations**: the tfvars deduction is closed over the gate **as read** — it assumes `terraform.tfvars` does not introduce a third term, and the gate has exactly two terms at `environments/staging/main.tf:115-117`. It also assumes live state was applied from this config, which the `ManagedBy=terraform` tags on the NAT and the secrets support. No tfvars content was read.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-08 — two Fargate services on ARM64; Postgres 16.x; MySQL 8.4.x

- **Claim ID**: ARCH-08
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (migration half)
- **Intended state**: two FARGATE services on ARM64, Postgres 16.x, MySQL fixture 8.4.x.
- **Repository-configured state**: two `FARGATE` services via `modules/ecs-service`, `cpu_architecture = ARM64`; `module.rds_postgres` engine default `16.4` (`terraform/modules/rds-postgres/variables.tf:20`); `module.rds_mysql` default `8.4.10` (`terraform/modules/rds-mysql/variables.tf:20`).
- **Observed deployed state**: both services `launchType: FARGATE`, `capacityProviderStrategy: null`, `status: ACTIVE`. `runtimePlatform` on **both** families: `{"cpuArchitecture": "ARM64", "operatingSystemFamily": "LINUX"}`; `networkMode: awsvpc`; `requiresCompatibilities: ["FARGATE"]`. All three running tasks `platformVersion: 1.4.0`, `connectivity: CONNECTED`. `intellichoice-staging-postgres`: `Engine: postgres`, `EngineVersion: 16.4`. `intellichoice-staging-mysql`: `Engine: mysql`, `EngineVersion: 8.4.10`.
- **Evidence source**: `aws ecs describe-services --cluster intellichoice-staging --services intellichoice-staging-learning-api intellichoice-staging-chat-api --query 'services[].[serviceName,launchType,capacityProviderStrategy,status]'` / `aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api --query 'taskDefinition.runtimePlatform'` / `aws rds describe-db-instances`
- **Observed at**: 2026-08-20T00:04Z (LANE-A)
- **Limitations**: `runtimePlatform: ARM64` is the task-definition **declaration** — the value Fargate schedules on, but control-plane metadata, not a `uname -m` from inside the container. Whether pgvector's HNSW index exists is inside the database and is not reachable read-only (see WORK-20, §3).
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-10 — learning-api's live desired/running count and the scalable target's MinCapacity

- **Claim ID**: ARCH-10
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: the configured floor of 2 is the live floor; `autoscaling_min_capacity`, not `desired_count`, is what moves live off 1.
- **Repository-configured state**: `desired_count = 2` and `autoscaling_min_capacity = 2` at `terraform/environments/staging/main.tf:446-447`, with the comment at `:443-445` recording that `desired_count` is in `ignore_changes`; module defaults 1/1 (`modules/ecs-service/variables.tf:68`, `:190`); `capacity_floors.learning-api.min_capacity = 2` at `main.tf:825-828`.
- **Observed deployed state**: service `desiredCount: 2`, `runningCount: 2`, `pendingCount: 0`. Scalable target `service/intellichoice-staging/intellichoice-staging-learning-api`: **`MinCapacity: 2`**, `MaxCapacity: 3`, `CreationTime: 2026-07-24T19:28:45Z`, `SuspendedState` all `false`. `list-tasks` returned exactly 2 ARNs (`5384e11b7cbd4054b9bda2dc23879941`, `de4e63c08f68437396398295b264a959`), both `lastStatus: RUNNING` on `…-learning-api:150`, `cpu: "512"`, `memory: "1024"`, one in `us-east-1a` (started 2026-08-18T18:47:17Z), one in `us-east-1b` (18:47:35Z).
- **Evidence source**: `aws ecs describe-services --cluster intellichoice-staging --services intellichoice-staging-learning-api` / `aws application-autoscaling describe-scalable-targets --service-namespace ecs` / `aws ecs list-tasks --cluster intellichoice-staging --service-name intellichoice-staging-learning-api` / `aws ecs describe-tasks --cluster intellichoice-staging --tasks <2 arns>`
- **Observed at**: 2026-08-20T00:03Z–00:04Z (LANE-A)
- **Limitations**: the terraform `desired_count = 2` literal is **unfalsifiable against AWS by design** — under `ignore_changes = [desired_count]` the live value is owned by Application Auto Scaling, so `desiredCount: 2` corroborates `MinCapacity: 2`, not the literal. `healthStatus` is `UNKNOWN` on all tasks (no container-level `healthCheck` is defined; readiness is judged by the ALB target group).
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-11 — StepScaling on ALB p95 with no CPU target-tracking; deployed min/max

- **Claim ID**: ARCH-11
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: latency step-scaling policies driven by p95 ALB alarms, with zero CPU target-tracking policies, min 1 / max 3 for chat-api.
- **Repository-configured state**: `enable_latency_step_scaling = true` for chat-api at `terraform/environments/staging/main.tf:544` **and for learning-api at `:457`** (S43/AUD-F-28 moved learning-api onto the same mechanism); the CPU policy is `count`-ed out; module default `false` (`modules/ecs-service/variables.tf:213`); the D-344 `autoscaling_max_capacity = 1` stopgap is reverted and its own comment at `main.tf:547-552` says it was never applied.
- **Observed deployed state**: **exactly four** scaling policies across both services, **all `PolicyType: StepScaling`; zero `TargetTrackingScaling`**. `…-chat-api-p95-latency-scale-out` and `…-learning-api-p95-latency-scale-out`: +1 on [0,7), +2 on [7,∞), cooldown 120; both `-scale-in`: −1 on (−∞,0], cooldown 300. All four `MetricAggregationType: Average`, `AdjustmentType: ChangeInCapacity`. `CreationTime`: chat-api pair 2026-07-29T04:17:02Z, learning-api pair 2026-07-30T18:32:10Z. chat-api scalable target `MinCapacity: 1`, **`MaxCapacity: 3`** — not the D-344 value of 1. Policies fire for real: chat-api `Setting desired count to 3.` at 2026-08-18T22:10:07Z, down to 2 at 22:26:39Z and to 1 at 22:32:39Z, plus six further scale events on 2026-08-16/17. Alarm thresholds from the LANE-B dump: `…-chat-api-p95-latency` **20.0 s** vs `…-learning-api-p95-latency` **3.0 s** (per-service override).
- **Evidence source**: `aws application-autoscaling describe-scaling-policies --service-namespace ecs` / `aws application-autoscaling describe-scalable-targets --service-namespace ecs` / `aws application-autoscaling describe-scaling-activities --service-namespace ecs --resource-id service/intellichoice-staging/intellichoice-staging-chat-api --max-results 10` / `aws cloudwatch describe-alarms --max-records 100`
- **Observed at**: 2026-08-20T00:04Z–00:05Z (LANE-A); alarm thresholds 00:04:06Z (LANE-B)
- **Limitations**: the claim is *worded* as if the latency policy were chat-api's alone; deployed reality — and `main.tf:457` — is that **both** services carry it (LOW wording note, no drift entry). `describe-scaling-activities` returns a bounded window; older activity is not shown. This block confirms the F-03 example empirically: D-344's `max = 1` was never applied.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-12 — task definitions omit `command`/`entryPoint`; learning-api's app container pinned to 384 CPU

- **Claim ID**: ARCH-12
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (config half)
- **Intended state**: no `command`/`entryPoint` override (so the image CMD's single uvicorn worker runs); learning-api's app container holds 384 of 512 units, leaving 128 to the sidecar.
- **Repository-configured state**: no `command`/`entryPoint` in either container definition; image CMDs carry no `--workers`; learning-api `cpu = 512` / `memory = 1024` (`main.tf:430-431`) with `pin_app_container_cpu = true` (`:438`); `otel_collector_cpu` default 128 / `otel_collector_memory` 256 (`modules/ecs-service/variables.tf:250-258`); chat-api on module defaults 256/512 (`:56`, `:62`).
- **Observed deployed state**, on the service-pinned revisions: `learning-api:150` task `512`/`1024` — container `learning-api` cpu **384**, memory `null`, `command` **`null`**, `entryPoint` **`null`**; container `otel-collector` cpu **128**, memory 256. `chat-api:148` task `256`/`512` — container `chat-api` cpu **0** (the unpinned case, module default `pin_app_container_cpu = false`), `command`/`entryPoint` both `null`; `otel-collector` 128/256. `ops-task:144` task `256`/`512`, container cpu 0, `command: ["true"]` — the deliberate placeholder entrypoint for the scheduler-overridden ops container. `memoryReservation` and `healthCheck` are `null` on all app containers. 384 + 128 = 512, the task total.
- **Evidence source**: `aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api:150 --query 'taskDefinition.[cpu,memory,containerDefinitions[].{name:name,cpu:cpu,memory:memory,command:command,entryPoint:entryPoint}]'` (and `intellichoice-staging-chat-api:148`, `intellichoice-staging-ops-task`)
- **Observed at**: 2026-08-20T00:04Z (LANE-A)
- **Limitations**: says nothing about the uvicorn worker count actually running inside the container — that is an image-CMD property, verifiable only by inspecting the image or its process table. The measured throughput figures (≈5 concurrent/task, concurrency^1.55) are load measurements → 3B-2. `cpu: 0` on chat-api means "no reservation": the 256 task units are shared by CFS weight between app and sidecar — an observation, not a defect.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-13 — deployed MaxCapacity per service; live task count; is the ceiling really 3?

- **Claim ID**: ARCH-13
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: learning-api min 2 / max 3, chat-api min 1 / max 3; "today = 2 tasks" holds live.
- **Repository-configured state**: learning-api min 2 / max 3 (module default `autoscaling_max_capacity = 3`, `modules/ecs-service/variables.tf:196`); chat-api min 1 / max 3. The withdrawn D-153 §3 five-task plan would have exceeded the ceiling.
- **Observed deployed state**: `service/…/intellichoice-staging-learning-api` Min 2 / **Max 3**, desired 2, running 2; `service/…/intellichoice-staging-chat-api` Min 1 / **Max 3**, desired 1, running 1. Cluster `runningTasksCount: 3`, `activeServicesCount: 2`. The ceiling is not merely configured but **reached and respected**: learning-api `Setting desired count to 3.` at **2026-08-19T22:19:09Z** (cause `…-learning-api-p95-latency-scale-out` in ALARM), back to 2 at 22:34:49Z, same pattern on 2026-08-16; chat-api reached 3 on 2026-08-18T22:10:07Z and 2026-08-17T06:19:22Z.
- **Evidence source**: `aws application-autoscaling describe-scalable-targets --service-namespace ecs --resource-ids service/intellichoice-staging/intellichoice-staging-learning-api service/intellichoice-staging/intellichoice-staging-chat-api` / `aws ecs describe-services --cluster intellichoice-staging --services … --query 'services[].[serviceName,desiredCount,runningCount]'` / `aws application-autoscaling describe-scaling-activities --service-namespace ecs --resource-id service/intellichoice-staging/intellichoice-staging-learning-api --max-results 10`
- **Observed at**: 2026-08-20T00:04Z–00:05Z (LANE-A)
- **Limitations**: `MaxCapacity: 3` is the Application Auto Scaling ceiling only; Fargate account quotas could bind lower under a real burst and were not read. The running counts are a point-in-time snapshot.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-14 — live `DBInstanceClass` and `MultiAZ`

- **Claim ID**: ARCH-14
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: `db.t4g.micro` on both engines, `MultiAZ` false.
- **Repository-configured state**: `default = "db.t4g.micro"` in `terraform/modules/rds-postgres/variables.tf:23-33` and `modules/rds-mysql/variables.tf:23-31` with no environment override (no `instance_class` assignment at `environments/staging/main.tf:248` or `:257`); `multi_az` default `false`; `allocated_storage_gb` default 20 in both.
- **Observed deployed state**, both instances identical unless noted: `DBInstanceClass` **`db.t4g.micro`**; postgres `16.4` / mysql `8.4.10`; `MultiAZ` **`false`**; `AllocatedStorage` 20, `StorageType` `gp3`; `DBName` `intellichoice`; `PubliclyAccessible` `false`; **`BackupRetentionPeriod` 1**; `DBInstanceStatus` `available`; `InstanceCreateTime` 2026-07-23T01:09:10Z (postgres) / 01:09:18Z (mysql); `AvailabilityZone` **`us-east-1a` on both**; parameter groups `default.postgres16` / `default.mysql8.4` (AWS defaults, no custom group); `StorageEncrypted` `true`; **`DeletionProtection` `false`**; `PerformanceInsightsEnabled` `false`.
- **Evidence source**: `aws rds describe-db-instances --query 'DBInstances[].{id:DBInstanceIdentifier,class:DBInstanceClass,engine:Engine,version:EngineVersion,multiAZ:MultiAZ,storage:AllocatedStorage,storageType:StorageType,dbName:DBName,public:PubliclyAccessible,backupRetention:BackupRetentionPeriod,status:DBInstanceStatus,created:InstanceCreateTime,az:AvailabilityZone,pg:DBParameterGroups[].DBParameterGroupName,encrypted:StorageEncrypted,deletionProtection:DeletionProtection,perfInsights:PerformanceInsightsEnabled}'`
- **Observed at**: 2026-08-20T00:04Z (LANE-A)
- **Limitations**: three facts the claim did not ask about came back on the same call and are recorded as a new observation, not as drift against this claim — 1-day backup retention, deletion protection off, and both instances in the same AZ (see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-09). `describe-db-parameters` was not run: with default parameter groups there is nothing repo-configured to compare against.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-15 — are Free-Tier restrictions active, and does the claimed `CreateDBInstance` rejection exist?

- **Claim ID**: ARCH-15
- **Previous repository-side classification**: **UNVERIFIED** — one of the two 3A could not classify
- **Intended state**: per the repo comment, "this AWS account has Free Tier restrictions active (confirmed via a real CreateDBInstance rejection during S32/D-084)".
- **Repository-configured state**: a **self-report only** — the comment at `terraform/modules/rds-postgres/variables.tf:25-28`. 3A classified it UNVERIFIED because it is the repo testifying about itself.
- **Observed deployed state**: **the rejection exists, and it refutes the claim.** Exactly three `CreateDBInstance` events in the 90-day window (which reaches back to 2026-05-22 — **nothing has aged out**), all by `jeongsik-staging-admin`: (1) 2026-07-23T01:03:47Z, `intellichoice-staging-mysql`, class **`db.t4g.micro`**, engine mysql **8.4.3**, `errorCode` **`InvalidParameterCombinationException`**, `errorMessage` **`Cannot find version 8.4.3 for mysql`**; (2) 2026-07-23T01:05:44Z postgres 16.4 at `db.t4g.micro` — succeeded; (3) 2026-07-23T01:05:45Z mysql **8.4.10** at `db.t4g.micro` — succeeded. The single rejection is an **engine-version typo**, requested at the micro class already, retried ~2 minutes later and successful. **No `CreateDBInstance` rejection anywhere in the window is attributable to Free-Tier restrictions or instance size.** `freetier get-free-tier-usage` returns 16 rows, **every one `freeTierType: "Always Free"` — no `"12 Month Free"` row of any kind**, notably no RDS `db.t*.micro` 750-hour row.
- **Evidence source**: `aws freetier get-free-tier-usage --region us-east-1` / `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=CreateDBInstance --start-time 2026-05-22T00:10:23Z --max-results 50` (then each event's full `CloudTrailEvent` JSON read for `errorCode` / `errorMessage` / `requestParameters`) / `aws ce get-cost-and-usage --time-period Start=2026-08-01,End=2026-08-20 --granularity MONTHLY --metrics UnblendedCost UsageQuantity --group-by Type=DIMENSION,Key=USAGE_TYPE --filter '{"Dimensions":{"Key":"SERVICE","Values":["EC2 - Other"]}}'`
- **Observed at**: 2026-08-20T00:10:20Z–00:12Z (LANE-C)
- **Limitations**: `lookup-events` covers 90 days and indexes management events only — adequate here, since `CreateDBInstance` is one and the S32 window is inside it. The broader proposition "are Free-Tier restrictions active" has **no first-class describe API**, so the absence of `12 Month Free` rows is strong but *indirect* evidence. The `db.t4g.micro` choice itself remains sound; only the stated justification is refuted. This does **not** close as "unfalsifiable read-only" — the record was retrieved in full, so the claim is falsifiable and is falsified on its own stated evidence.
- **Classification**: DEPLOYED_DIFFERS_FROM_REPOSITORY (see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-06 — WEAKENS the Phase-2/3A ARCH-15 claim)

#### ARCH-22 — instance-level `DBName` on both engines

- **Claim ID**: ARCH-22
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: `DBName` is `intellichoice` on the Postgres instance, and the MySQL fixture carries the same name on a different engine.
- **Repository-configured state**: `db_name` default `"intellichoice"` on both modules (`modules/rds-postgres/variables.tf:52-55`, `modules/rds-mysql/variables.tf:43-46`), no override; threaded to `LEARNING_DB_NAME` / `CHAT_DB_NAME`.
- **Observed deployed state**: `intellichoice-staging-postgres` `Engine: postgres`, **`DBName: intellichoice`**; `intellichoice-staging-mysql` `Engine: mysql`, **`DBName: intellichoice`**. learning-api:150 env: `LEARNING_DB_NAME = "intellichoice"`, `LEARNING_DB_PORT = "5432"`, `LEARNING_DB_HOST = "intellichoice-staging-postgres.co9ok4sc8ugb.us-east-1.rds.amazonaws.com"`, `LEARNING_MYSQL_DB_HOST = "intellichoice-staging-mysql.co9ok4sc8ugb.us-east-1.rds.amazonaws.com"`, `LEARNING_MYSQL_DB_PORT = "3306"`. chat-api:148 env: `CHAT_DB_NAME = "intellichoice"`, `CHAT_DB_PORT = "5432"`, the same two hosts, `CHAT_MYSQL_DB_PORT = "3306"`.
- **Evidence source**: `aws rds describe-db-instances --query 'DBInstances[].[DBInstanceIdentifier,Engine,DBName,Endpoint.Address]'` / `aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api:150 --query 'taskDefinition.containerDefinitions[0].environment'`
- **Observed at**: 2026-08-20T00:04Z (LANE-A)
- **Limitations**: enumerating the databases *inside* each instance needs a DB connection → forbidden (§3). `DBName` is the instance's initial-database attribute; it does not prove the application is connected to that database today — that is a 3B-2 behavioural question.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-28 — NAT count, the private default route, and the VPC endpoints

- **Claim ID**: ARCH-28
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: PrivateLink endpoints exist with the interface ones in a single subnet; the claim's "zero NAT" property was already known false under checked-in defaults.
- **Repository-configured state**: `aws_route_table.private` carries **no inline route**; the only default route is the counted `aws_route "private_nat"` (`terraform/modules/vpc/main.tf:96-110`, split out deliberately per the comment at `:102-104`). Endpoints `["ecr.api","ecr.dkr","logs","secretsmanager"]` + conditional `bedrock-runtime` + conditional `xray` (`:143-160`), all pinned to `subnet_ids = [aws_subnet.private[0].id]` for the per-AZ-per-hour cost reason at `:168-173`, plus the free S3 **Gateway** endpoint on the private route table (`:183-191`).
- **Observed deployed state**: **NAT count = 1** (see ARCH-29). **Three route tables.** `rtb-0ae773acec1e7ee86` = `intellichoice-staging-private-rt`, associated to *both* private subnets, with three active routes: `10.0.0.0/16 -> local`; **`0.0.0.0/0 -> nat-07ab02d5cd28b6f72`** (active); `pl-63a5400a -> vpce-0ff6eac093f3b8c3b`. `rtb-04208e04793eb53e3` = public-rt, `0.0.0.0/0 -> igw-0a7cf5e77437601c5`. `rtb-06daf0ec1bd4494de` is the VPC main table: `local` only, **zero subnet associations**. **Seven VPC endpoints, all `available`** — 6 Interface (`ecr.api` `vpce-00353f0d62f938951`, `ecr.dkr` `vpce-00a9d3ce72585f9b7`, `logs` `vpce-0aca320aa29af3ae5`, `secretsmanager` `vpce-04f438eabd47ae09b`, `bedrock-runtime` `vpce-08205174d558bf572`, `xray` `vpce-0eddc50065abc827f`), **all in the single subnet `subnet-0fab49a3bf8fc3a8f`** (private, us-east-1a), `PrivateDns` true — plus the S3 **Gateway** endpoint `vpce-0ff6eac093f3b8c3b` on the private route table. No `bedrock-mantle` endpoint. **Three EIPs, all associated**: `eipalloc-0715fd3228e854c56` → `eni-02a5fb06297ad95e0` Name=`intellichoice-staging-nat-eip`; the two untagged ones resolve via `describe-network-interfaces` to the ALB's two per-AZ ENIs (`ELB app/intellichoice-staging-alb/a1e99fb6d592d3d4`). **No unassociated EIP** — COST-28's idle-EIP cost finding does not fire.
- **Evidence source**: `aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-094b422fba4f50e71` / `aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=vpc-094b422fba4f50e71` / `aws ec2 describe-addresses` / `aws ec2 describe-network-interfaces --network-interface-ids eni-0de355269cabde152 eni-0da256dda46714975` / `aws ec2 describe-internet-gateways --filters Name=attachment.vpc-id,Values=vpc-094b422fba4f50e71` / `aws ec2 describe-subnets --filters Name=vpc-id,Values=vpc-094b422fba4f50e71`
- **Observed at**: 2026-08-20T00:04:49Z (LANE-C)
- **Limitations**: AWS does not expose whether a route came from an inline `route` block or a standalone `aws_route` resource, so the **mechanism** half of this claim stays config-only evidence (`modules/vpc/main.tf:105-110`). Interface-endpoint DNS resolution *from the second AZ* is a runtime property not observable from the control plane. The claim's "zero NAT" reading is false in live as well as in config — exactly as 3A predicted from the defaults.
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-29 — does the deployed VPC hold a NAT gateway, and what does that do to D-419's sentence?

- **Claim ID**: ARCH-29
- **Previous repository-side classification**: PARTIALLY_IMPLEMENTED — DRIFT-29
- **Intended state**: ARCHITECTURE.md says "one NAT in one AZ, deliberately"; D-419 says the NAT was "absent from the plan entirely". These cannot both describe live.
- **Repository-configured state**: D-406's two-consumer gate — `private_egress_consumers = {langsmith_tracing = var.langsmith_tracing_enabled, youtube_sync = var.youtube_sync_enabled}` (`environments/staging/main.tf:115-117`), `needs_private_egress = anytrue(values(...))` (`:119`), `nat_gateway_enabled = local.needs_private_egress` (`:136`). `langsmith_tracing_enabled` defaults true → config evaluates to **count 1**.
- **Observed deployed state**: **exactly one NAT gateway, `state: available`.** The **unfiltered** call returned the same single element — there is no deleted or failed NAT in the account's history at all; this is the only NAT that has ever existed. `NatGatewayId: nat-07ab02d5cd28b6f72`; `SubnetId: subnet-07b390797f61497e8` (public, us-east-1a); `VpcId: vpc-094b422fba4f50e71`; **`CreateTime: 2026-08-07T04:47:31Z`**; `ConnectivityType: public`; `AvailabilityMode: zonal`; Tags `Name=intellichoice-staging-nat`, **`ManagedBy=terraform`**, `Environment=staging`, `Project=IntelliChoice`. Dating it against the two named commits: D-406 `15bb6b3` = 2026-08-18T07:52:56Z; D-419's apply `2e301d6` = 2026-08-18T20:32:35Z. **The NAT predates both by 11 days.** So `terraform plan` showed no NAT diff because there was nothing to change — D-419 was describing the plan diff, not NAT absence. ARCHITECTURE.md's "one NAT in one AZ, deliberately" is the accurate text.
- **Evidence source**: `aws ec2 describe-nat-gateways --output json` (unfiltered — includes deleted history) / `aws ec2 describe-nat-gateways --filter Name=state,Values=available,pending,deleting --query 'NatGateways[].[NatGatewayId,State,SubnetId,VpcId,CreateTime]'` / `git log -1 --format='%H %cI %s' 15bb6b3` / `git log -1 --format='%H %cI %s' 2e301d6`
- **Observed at**: 2026-08-20T00:04:13Z (LANE-C)
- **Limitations**: `CreateTime` dates the **resource**, not the commit that created it. The pre-D-406 config (`nat_gateway_enabled = var.langsmith_tracing_enabled`, quoted in the comment at `main.tf:104`/`:133`) would have produced an identical NAT, so the create time cannot distinguish *which version of the gate* applied it — only that it was not D-406/D-419.
- **Classification**: DEPLOYED_CONFIRMED (against config defaults; see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-05 for the D-419 wording)

#### ARCH-30 — the otel sidecar and the four Bedrock metric filters

- **Claim ID**: ARCH-30
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (masking half)
- **Intended state**: a non-essential `otel-collector` sidecar runs in each task, and four Bedrock metric filters exist per app log group.
- **Repository-configured state**: sidecar at `terraform/modules/ecs-service/main.tf:112` (name) / `:119` (`essential = false`), exporting OTLP → `awsxray`; `enable_otel_sidecar = var.enable_otel_tracing` at `environments/staging/main.tf:462` / `:555`; image built at `main.tf:56` from the private mirror with `otel_collector_version = "v0.43.3"` (`environments/staging/variables.tf:102-104`), overriding the module's public-ECR fallback (`modules/ecs-service/variables.tf:247`). Four filters `for_each = var.log_group_names` at `modules/observability/dashboard.tf:49/67/84/130`.
- **Observed deployed state**: **both** task definitions hold exactly two containers — the app container (`essential: true`) and **`otel-collector`** (`essential: false`, cpu 128, memory 256, no port mappings, one env var `AOT_CONFIG_CONTENT`). Sidecar image on both: `3205….dkr.ecr.us-east-1.amazonaws.com/aws-otel-collector:v0.43.3` — the **private mirror**. All three running tasks report the sidecar `lastStatus: RUNNING`, digest `sha256:ba3c3f060746be682b405cf1e43965d69b4c4491bb37a13f399c5860cf699545`, identical to the only image in that ECR repo. `AOT_CONFIG_CONTENT` confirms the live pipeline: receivers `otlp` (grpc `0.0.0.0:4317`, http `0.0.0.0:4318`) + `prometheus` scraping `localhost:8001`/`localhost:8002` `/metrics` every 60s; processors `filter/kpis` (a strict allow-list of **22** metric names) + `batch` (size 50, timeout 5s); exporters `awsemf` → `/ecs/intellichoice-staging-{learning,chat}-api/emf`, namespaces `IntelliChoice/intellichoice-staging/{learning-api,chat-api}`, `dimension_rollup_option: NoDimensionRollup`, plus `awsxray`. Both apps set `*_OTEL_ENABLED = "true"` and `*_OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4318"`. **All four Bedrock filters exist on BOTH app log groups** (8 instances), verbatim: `…-bedrock-cost-cents` `{ $.event = "bedrock_call" && $.cost_cents = * }` → `BedrockCostCents`, value `$.cost_cents`, default **ABSENT**, unit None; `…-bedrock-duration-ms` `{ $.event = "bedrock_call" && $.duration_ms = * }` → `BedrockCallDurationMs`, unit Milliseconds; `…-bedrock-call-failed` `{ $.event = "bedrock_call_failed" }` → `BedrockCallFailed`, value 1, default 0.0, Count; `…-bedrock-circuit-open` `{ $.event = "bedrock_call_failed" && $.reason = "circuit_open" }` → `BedrockCircuitOpen`, value 1, default 0.0, Count.
- **Evidence source**: `aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api:150 --query 'taskDefinition.containerDefinitions[].[name,essential,image]'` (and `chat-api:148`) / `aws ecs describe-tasks --cluster intellichoice-staging --tasks <3 arns> --query 'tasks[].containers[].[name,lastStatus,healthStatus,image,imageDigest]'` / `aws logs describe-log-groups --log-group-name-prefix /ecs/intellichoice-staging` / `aws logs describe-metric-filters --log-group-name /ecs/intellichoice-staging-learning-api` (and `-chat-api`)
- **Observed at**: 2026-08-20T00:04Z (LANE-A, sidecar); 00:04:48Z–00:04:59Z (LANE-B, filters)
- **Limitations**: `lastStatus: RUNNING` means the container process is up — it does **not** prove EMF metrics or X-Ray segments are being emitted (no container `healthCheck` is defined, so `healthStatus` is `UNKNOWN` everywhere). Both `/emf` log groups carry **zero** metric filters; nothing in the configured side claims otherwise. chat-api's collector allow-lists the full 22-metric set including the `learning_*` names — a shared-module artifact, so the chat-api namespace will simply never receive those series. Whether traffic "never leaves AWS" is a network property, out of scope. What LangSmith actually received is external (see SEC-23, §3).
- **Classification**: DEPLOYED_CONFIRMED

#### ARCH-34 — is each service's running task definition its family's latest revision?

- **Claim ID**: ARCH-34
- **Previous repository-side classification**: CONFIRMED_IN_REPOSITORY — DRIFT-80, partial
- **Intended state**: `scripts/check_deployed_image_consistency.py` would report no drift between the running task definition and its family's latest revision.
- **Repository-configured state**: `make image-check` at `Makefile:292-294`; `adopt_deployed_image` default `true` (`environments/staging/variables.tf:201-202`) consumed by the `for_each` guard at `main.tf:12`; image expression at `main.tf:45`/`:49` with `learning_api_image_tag` / `chat_api_image_tag` both defaulting to `"unset"` (`variables.tf:32-39`). Operator-invoked only — wired into neither CI nor `deploy-staging.yml`.
- **Observed deployed state**: **the service's revision is NOT its family's latest, on both services.** `intellichoice-staging-learning-api`: family latest **151** (`registeredAt` 2026-08-18T**20:20:41.514**Z) vs the service's **150** (18:46:27.648Z). `intellichoice-staging-chat-api`: latest **149** (20:20:41.514Z) vs service **148** (18:49:32.753Z). `intellichoice-staging-ops-task`: latest **144** (20:20:41.511Z), no service. All three latest revisions were registered within **3 milliseconds** of each other — the signature of a single `terraform apply`, ~1.5 h *after* the two service deployments were created; `ignore_changes = [task_definition]` prevented adoption. A normalised diff (ignoring `revision`/`registeredAt`/`taskDefinitionArn`/`registeredBy`) shows: **`chat-api:148` vs `:149` — byte-identical**; **`learning-api:150` vs `:151` — the only difference is the ordering of the `compatibilities` array** (`["MANAGED_INSTANCES","FARGATE"]` vs `["FARGATE","MANAGED_INSTANCES"]`), a server-side serialisation artifact. The un-adopted revisions are functionally no-ops: same image, cpu/memory, env, secrets, sidecar.
- **Evidence source**: `aws ecs describe-services --cluster intellichoice-staging --services intellichoice-staging-learning-api intellichoice-staging-chat-api --query 'services[].[serviceName,taskDefinition]'` / `aws ecs list-task-definitions --family-prefix intellichoice-staging-learning-api --sort DESC --max-items 5` (and `-chat-api`, `-ops-task`) / `aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api` (resolves to family LATEST) vs `…-learning-api:150`
- **Observed at**: 2026-08-20T00:04Z–00:06Z (LANE-A)
- **Limitations**: **the tfvars-staleness half of this claim is not answerable from AWS.** With `adopt_deployed_image = true`, the `data` source at `main.tf:12` reads the deployed image and the `var.*_image_tag` pin is bypassed, so pin staleness is invisible from the control plane; `environments/staging/terraform.tfvars` exists (7,917 bytes, mtime 2026-08-17 22:41) and its **content was not read**. `list-task-definitions --max-items 5` truncated (a `NextToken` was returned each time), so revisions below 147/145/140 were not enumerated. Whether the deploy-time version gate ever *fired* is GitHub state (see ARCH-33, §3).
- **Classification**: DEPLOYED_STATE_PARTIALLY_CONFIRMED (revision-number drift, not image drift; see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-11)

#### ARCH-35 — all three ORG_TIME env vars on both services, and is `ORG_TIME_CONFIRMED` still false?

- **Claim ID**: ARCH-35
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (config half)
- **Intended state**: `ORG_TIMEZONE`, `ORG_TIME_CONVENTION` and `ORG_TIME_CONFIRMED` on both task definitions, with `ORG_TIME_CONFIRMED` marking the org's hours as provisional.
- **Repository-configured state**: all three on both, `terraform/environments/staging/main.tf:497-499` (learning) and `:582-584` (chat); `ORG_TIME_CONFIRMED = var.org_time_confirmed ? "true" : "false"`.
- **Observed deployed state**: identical on **both** services — `ORG_TIMEZONE = America/Chicago`, `ORG_TIME_CONVENTION = local_dst_aware`, **`ORG_TIME_CONFIRMED = false`**. All three vars are present; the org's operating hours remain **provisional** in the deployed build.
- **Evidence source**: ``aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api:150 --query 'taskDefinition.containerDefinitions[0].environment[?starts_with(name, `ORG_TIME`)]'`` (and `chat-api:148`)
- **Observed at**: 2026-08-20T00:04Z (LANE-A)
- **Limitations**: env var names and non-secret values only. Shows what the task definition **declares**, not how the application interprets it.
- **Classification**: DEPLOYED_CONFIRMED

### 2.2 SEC family (4)

#### SEC-10 — do the eight `alarms.tf` alarms exist at staging cardinality, and what are their states?

- **Claim ID**: SEC-10
- **Previous repository-side classification**: PARTIALLY_IMPLEMENTED — named by F-03
- **Intended state**: eight alarm resources deployed at their expected staging cardinality; F-03 flagged that "eight alarms" was file state only.
- **Repository-configured state**: eight resource blocks in `terraform/modules/observability/alarms.tf:29-238` — `bedrock_circuit_open`, `langsmith_ingest_failed`, `bedrock_call_failed`, `rds_cpu`, `rds_free_storage`, `rds_connections`, `ecs_memory`, `bedrock_spend_spike` — most `for_each`-ed over services, log groups or DB instances.
- **Observed deployed state**: **all 8 present at ×2 each = 16 instances**, every one `OK`, with thresholds matching config: `bedrock_circuit_open` 0.0 GT / 300 s / ev 1; `langsmith_ingest_failed` 10.0 GT / 900 s / ev 2; `bedrock_call_failed` 5.0 GT / 300 s / ev 3; `rds_cpu` 80.0 GT / 300 s / ev 3; `rds_free_storage` 4294967296.0 (4 GiB) LT / 300 s / ev 2 / tmd `missing`; `rds_connections` postgres **80.0** / mysql **40.0** (per-engine, as configured); `ecs_memory` **716.0** MiB GT / 300 s / ev 3 (matches `ecs_memory_alarm_mib = 716`); `bedrock_spend_spike` 200.0 cents GT / 3600 s / ev 1. **The §7-R9 negative check:** no alarm anywhere references `learning_checkpoint_repairs_total` or `checkpoint_repair` (`{"checkpoint_repair_alarms": []}`), while the metric itself **exists with data** in both app namespaces — an instrumented-but-unalarmed tripwire.
- **Evidence source**: `aws cloudwatch describe-alarms --max-records 100 --output json` / `aws cloudwatch describe-alarms --state-value INSUFFICIENT_DATA` / `aws cloudwatch list-metrics --namespace IntelliChoice/intellichoice-staging/learning-api`
- **Observed at**: 2026-08-20T00:04:06Z (LANE-B)
- **Limitations**: `AlarmDescription` text was not diffed against config (not decision-relevant). Whether the RDS alarm dimensions point at the *right* instance identifiers was not cross-checked against `describe-db-instances`. "Eight alarms" is now runtime-verified; the tripwire gap is a coverage observation (see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-08).
- **Classification**: DEPLOYED_CONFIRMED (negative check runtime-proven)

#### SEC-16 — CloudTrail posture and live delivery

- **Claim ID**: SEC-16
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: `IsLogging: true`, multi-region, log-file validation on, no data-event selectors, 90-day bucket expiry, and log files actually being delivered.
- **Repository-configured state**: CloudTrail wired at `terraform/environments/staging/main.tf:743-748`; `is_multi_region_trail`, `include_global_service_events`, `enable_log_file_validation` all `true`; no `event_selector` block; bucket lifecycle `expiration { days = 90 }`, public-access block, SSE, versioning.
- **Observed deployed state**: **exactly one trail**, `intellichoice-staging-trail`, bucket `intellichoice-staging-cloudtrail-3205…`, `IsMultiRegionTrail: true`, `IncludeGlobalServiceEvents: true`, `LogFileValidationEnabled: true`, `HasCustomEventSelectors: false`, `HasInsightSelectors: false`, `IsOrganizationTrail: false`, `HomeRegion: us-east-1`. Status: **`IsLogging: true`**, `StartLoggingTime: 2026-07-30T20:29:59Z`, `TimeLoggingStopped: ""`, `LatestDeliveryTime` / `LatestDeliveryAttemptTime` / **`LatestDeliveryAttemptSucceeded: 2026-08-20T00:06:12Z`** (~90 seconds before the call), `LatestDigestDeliveryTime: 2026-08-19T23:38:22Z`; **no `LatestDeliveryError` field is present at all**. Event selectors: one, `ReadWriteType: All`, `IncludeManagementEvents: true`, **`DataResources: []`** — management events only. Bucket: lifecycle rule `expire-trail-logs` Enabled, prefix `""`, `Expiration.Days = 90`, `NoncurrentVersionExpiration.NoncurrentDays = 90`, `AbortIncompleteMultipartUpload.DaysAfterInitiation = 7`; versioning `Enabled`; all four public-access-block flags true; encryption `AES256` (SSE-S3). Delivery objects exist under `AWSLogs/`, e.g. a 355-byte `…/CloudTrail-Digest/ap-northeast-1/2026/07/30/…json.gz` then 724/720/721 bytes — an `ap-northeast-1` path from a `us-east-1` home region is independent proof that multi-region is *functioning*, not merely set.
- **Evidence source**: `aws cloudtrail describe-trails` / `aws cloudtrail get-trail-status --name intellichoice-staging-trail` / `aws cloudtrail get-event-selectors --trail-name …` / `aws cloudtrail get-insight-selectors --trail-name …` / `aws s3api get-bucket-lifecycle-configuration --bucket …` / `get-bucket-versioning` / `get-public-access-block` / `get-bucket-encryption` / `aws s3api list-objects-v2 --bucket … --prefix AWSLogs/ --max-items 5`
- **Observed at**: 2026-08-20T00:07:28Z–00:07:40Z (LANE-C)
- **Limitations**: the queue predicted a "1,761-byte `.json.gz` delivery proof"; the first five keys are **digest** files of 355–724 bytes. That is a lexicographic-ordering artifact (`CloudTrail-Digest/` sorts before `CloudTrail/` and `--max-items 5` never reached the event logs), not a discrepancy — delivery is established by `LatestDeliveryAttemptSucceeded` and the digests. Bucket **policy** statements (the two `aws:SourceArn` conditions) were not read; `get-bucket-policy` was not run, so that half stays config-only. `get-insight-selectors` returned `InsightNotEnabledException`, the expected no-extra-cost posture.
- **Classification**: DEPLOYED_CONFIRMED

#### SEC-25 — dev-token endpoints disabled, `*_ENVIRONMENT` = staging, shared-secret ARNs wired

- **Claim ID**: SEC-25
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (gate logic)
- **Intended state**: both dev-token flags `"false"` live, both environments `staging`, and two distinct per-service shared-secret ARNs wired into `secrets`.
- **Repository-configured state**: `app_environment` default `"staging"` (`environments/staging/variables.tf:68-70`); `*_DEV_TOKEN_ENDPOINT_ENABLED = "false"` at `main.tf:471` (D-085 rationale at `:467-470`) and `:561`; two distinct 64-char `random_password` secrets referenced as ARNs; `deploy-staging.yml:503+` asserts live unreachability without the secret.
- **Observed deployed state**, verbatim non-secret env: `LEARNING_DEV_TOKEN_ENDPOINT_ENABLED = "false"`, `CHAT_DEV_TOKEN_ENDPOINT_ENABLED = "false"`, `LEARNING_ENVIRONMENT = "staging"`, `CHAT_ENVIRONMENT = "staging"`. `secrets` blocks — **names and ARNs only, no value resolved** — 7 entries each. learning-api:150: `LEARNING_STAGING_TOKEN_SHARED_SECRET` → `arn:aws:secretsmanager:us-east-1:3205…:secret:intellichoice-staging/learning-api/staging-token-shared-secret-vo3lst`; `LEARNING_JWT_SIGNING_SECRET` → `…:secret:intellichoice-staging/learning-api/jwt-signing-secret-foYdVh`; `LANGSMITH_API_KEY` → `…:secret:intellichoice-staging/langsmith-api-key-zIsu7D`; DB pairs from the **RDS-managed** secrets `rds!db-13a43ef4-…-6ti5m8` and `rds!db-65bd7cf7-…-yYOmVA`. chat-api:148: `CHAT_STAGING_TOKEN_SHARED_SECRET` → `…:secret:intellichoice-staging/chat-api/staging-token-shared-secret-oT74Ug`; `CHAT_JWT_SIGNING_SECRET` → `…-YcKNRa`; the same LangSmith key and the same two `rds!db-*` pairs. So the two services share one LangSmith secret and both RDS master-credential secrets while holding **separate** JWT signing secrets and **distinct** shared secrets. Non-secret LangSmith identifiers present as plain env: `LANGSMITH_TRACING = "true"`, `LANGSMITH_PROJECT = "intellichoice-staging"`, `LANGSMITH_WORKSPACE_ID = "ccf03d37-9f18-4ca0-95ff-aaf0c02a0c60"`.
- **Evidence source**: `aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api:150 --query 'taskDefinition.containerDefinitions[0].{env:environment,secrets:secrets}'` (and `chat-api:148`)
- **Observed at**: 2026-08-20T00:04Z (LANE-A)
- **Limitations**: **no secret value was resolved and no `get-secret-value` was issued.** The "`/dev/token` returns 404 on the live ALB without the shared secret" assertion is an HTTP probe → 3B-2. The DB credentials come from AWS-managed `rds!db-*` secrets, which can carry their own rotation schedule independent of terraform — relevant to SEC-26's contrast.
- **Classification**: DEPLOYED_CONFIRMED

#### SEC-26 — were the two staging shared secrets rotated after the 2026-08-13 D-310 exposure?

- **Claim ID**: SEC-26
- **Previous repository-side classification**: **UNVERIFIED** — DRIFT-84; one of the two 3A could not classify
- **Intended state**: after a process-table exposure of both shared secrets on 2026-08-13, a rotated secret would show a version created after that date.
- **Repository-configured state**: no evidence of rotation — `git log -S"staging_token_shared_secret" -- terraform` returns exactly one commit ever (`168de30`, original creation); no `keepers`, no rotation trigger, no `aws_secretsmanager_secret_rotation` resource anywhere. Rotation performed outside terraform would leave no repo trace, so repo absence was weak negative evidence only.
- **Observed deployed state**: eight secrets in the account. For `intellichoice-staging/learning-api/staging-token-shared-secret`: `CreatedDate 2026-07-24T21:06:18.933Z`, **`LastChangedDate 2026-07-24T21:06:19.391Z`**, **`LastRotatedDate null`**, `RotationEnabled null`, `RotationRules null`, `RotationLambdaARN null`, `DeletedDate null`, `VersionIdsToStages` = one AWSCURRENT version, `list-secret-version-ids --include-deprecated` → **exactly 1 version**, created 2026-07-24T21:06:19.387Z. For `…/chat-api/staging-token-shared-secret`: `CreatedDate 2026-07-24T21:06:19.026Z`, **`LastChangedDate 2026-07-24T21:06:19.411Z`**, `LastRotatedDate null`, `RotationEnabled null`, **exactly 1 version**, created 2026-07-24T21:06:19.407Z. Both tagged `ManagedBy=terraform`. The specified test — "more than one version with a create date after 2026-08-13" — returns **zero such versions on both**. `LastChangedDate` is **20 days before** the exposure. Both are **actively read** (`LastAccessedDate` 2026-08-17 / 2026-08-18), so the exposed value is live and AWSCURRENT. **Contrast, from the same call:** the two AWS-managed `rds!db-*` secrets have `RotationEnabled: true` and were genuinely rotated on **2026-08-14** — the day after the exposure. Rotation demonstrably works in this account; its absence here is a gap in this project's provisioning, not an account capability limit.
- **Evidence source**: `aws secretsmanager list-secrets --max-results 100 --query 'sort_by(SecretList,&Name)[].{Name:Name,Created:CreatedDate,LastChanged:LastChangedDate,LastRotated:LastRotatedDate,LastAccessed:LastAccessedDate,RotationEnabled:RotationEnabled}'` / `aws secretsmanager describe-secret --secret-id intellichoice-staging/{learning-api,chat-api}/staging-token-shared-secret` / `aws secretsmanager list-secret-version-ids --secret-id <each> --include-deprecated`
- **Observed at**: 2026-08-20T00:07:58Z–00:08:10Z (LANE-C)
- **Limitations**: **metadata only — no `get-secret-value`; the only secret-adjacent strings recorded anywhere are AWS-generated opaque version identifiers.** `LastChangedDate` and version history prove no *Secrets Manager* rotation occurred; they cannot prove the exposed value was never invalidated by some other means — though SEC-25 shows the task definitions still point at these same ARNs, so the values are consumed as-is. `LastAccessedDate` has day granularity. Rotation performed and then reverted to the same value would still show >1 version, so the single-version finding is robust. Rotating is a mutation and was not attempted.
- **Classification**: DEPLOYED_CONFIRMED — resolves 3A's UNVERIFIED to runtime-confirmed NOT ROTATED (see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-02)

### 2.3 COST family (13)

#### COST-15 — current month-to-date spend by service

- **Claim ID**: COST-15
- **Previous repository-side classification**: deferred to 3B, §4.1 (aged-by-design)
- **Intended state**: a current spend baseline, if 3B needed one.
- **Repository-configured state**: none — §9's line is "re-run only if a current baseline needed". There is no repository-side figure to compare against, so this block records a baseline rather than a config comparison.
- **Observed deployed state**, period 2026-08-01 … 2026-08-20: `Claude Haiku 4.5 (Amazon Bedrock Edition)` **$19.63850882**; `Tax` **$1.30**; `Amazon Elastic Container Service` **$0.0378013638**; total net **$20.9385076161 USD**. Only those three service lines exceed $0.01 — **no `EC2 - Other`, NAT-Gateway, RDS, ALB, CloudWatch or S3 line** appears in the >$0.01 set. By `RECORD_TYPE`: **`Usage $249.9294156351`, `Tax $1.30`, `Credit $-230.290908019`**. The cost profile is Bedrock-dominated: Haiku 4.5 is 93.8% of net MTD spend, and all AWS infrastructure together is $0.038 of *visible* net cost.
- **Evidence source**: `aws ce get-cost-and-usage --time-period Start=2026-08-01,End=2026-08-20 --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE` / the same without `--group-by` / the same with `--group-by Type=DIMENSION,Key=RECORD_TYPE`
- **Observed at**: 2026-08-20T00:06:50Z / 00:07:43Z (LANE-B)
- **Limitations**: three Cost Explorer calls were made (each carries a small per-request charge; call count was kept low as instructed). `UnblendedCost` at MONTHLY granularity only — no daily decomposition. Month-to-date figures are flagged `Estimated: true`. The absence of a NAT usage line here is *net* accounting, not absence of the resource — LANE-C's `describe-nat-gateways` and the `USAGE_TYPE` read (COST-28) are authoritative, and they show the NAT's gross cost fully offset by credits.
- **Classification**: DEPLOYED_CONFIRMED (baseline observed; no repository-side assertion exists to differ from)

#### COST-16 — the AWS Budget, its notifications, and whether it can warn

- **Claim ID**: COST-16
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (settings-declaration half)
- **Intended state**: a monthly budget at the configured limit with two notifications (ACTUAL > 80%, FORECASTED > 100%) and a confirmed email subscriber.
- **Repository-configured state**: `aws_budgets_budget.monthly` (`terraform/modules/observability/main.tf:1-23`), `name = "${var.name_prefix}-monthly-budget"`, `limit_amount = tostring(var.monthly_budget_usd)` (default 20), `MONTHLY`, `COST`; two notifications, both emailing `var.notification_email`.
- **Observed deployed state**: `BudgetName: intellichoice-staging-monthly-budget`, `BudgetType: COST`, `TimeUnit: MONTHLY`, `BudgetLimit: {"Amount":"20.0","Unit":"USD"}`, **`CalculatedSpend.ActualSpend: {"Amount":"20.939","Unit":"USD"}`**, `CostFilters: {}`, `CostTypes: {IncludeCredit: true, IncludeRefund: true, UseAmortized: false}`, `LastUpdatedTime: 2026-08-19T15:48:57Z`. Notifications exactly as configured: `ACTUAL GREATER_THAN 80.0 PERCENTAGE` → **`NotificationState: ALARM`**; `FORECASTED GREATER_THAN 100.0 PERCENTAGE` → `OK`. Subscriber on both: `EMAIL k***@gmail.com`. **Two live facts the claim did not anticipate:** (1) the budget is already breached — $20.939 against a $20.00 limit (104.7%) — while the FORECASTED>100% notification still reads OK; (2) a **second, non-repo-managed** budget exists, `"My Monthly Cost Budget"`, $10.00 limit, `ActualSpend $251.229`, `CostFilters: null`, three notifications (ACTUAL>100 ALARM, ACTUAL>85 ALARM, FORECASTED>100 OK), `LastUpdatedTime 2026-08-19T15:56:54Z` — console-created, not in terraform. The 12× gap is fully explained by `IncludeCredit: true`: the repo budget measures post-credit $20.94, the console budget measures gross $251.23, against `Usage $249.93` / `Credit $-230.29`.
- **Evidence source**: `aws budgets describe-budgets --account-id 3205…` / `aws budgets describe-budget --account-id 3205… --budget-name intellichoice-staging-monthly-budget` / `aws budgets describe-notifications-for-budget --account-id 3205… --budget-name …` / `aws budgets describe-subscribers-for-notification --account-id 3205… --budget-name … --notification '<each>'` / `aws ce get-cost-and-usage --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=RECORD_TYPE`
- **Observed at**: 2026-08-20T00:05:19Z / 00:05:38Z / 00:07:18Z / 00:07:43Z (LANE-B)
- **Limitations**: credit **expiry** is not exposed by any read-only API, so *when* the post-credit step change lands cannot be predicted from this data. The LOW config drift already recorded against this claim (the runbook's "scale `desired_count` to 0" lever being ineffective under `ignore_changes` + autoscaling min) was settled in 3A; nothing in AWS contradicts it and the operative knob remains `autoscaling_min_capacity`. See `DEPLOYED_INFRA_DRIFT_REGISTER` RD-03.
- **Classification**: DEPLOYED_CONFIRMED (configuration half; the breach and the credit masking are new runtime observations)

#### COST-17 — the `client_errors` filter and per-service alarm on the page channel

- **Claim ID**: COST-17
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (reporting half)
- **Intended state**: a `client_error` metric filter with `default_value = 0` per app log group, and a per-service alarm routing to the **page** topic.
- **Repository-configured state**: filter `client_errors`, pattern `{ $.event = "client_error" }`, metric `ClientErrors`, `default_value = 0` (`app_events.tf:40-43`); alarm `for_each = var.log_group_names`, `period = 900`, `Sum`, `treat_missing_data = "notBreaching"`, `alarm_actions = [aws_sns_topic.alerts.arn]` (`app_events.tf:45-72`).
- **Observed deployed state**: filter `intellichoice-staging-learning-api-client-errors`, pattern **`{ $.event = "client_error" }`** → `IntelliChoice/intellichoice-staging/learning-api / ClientErrors`, `value=1`, **`default=0.0`**, `unit=None`, `dims={}`; the chat-api filter is identical in its own namespace. Alarms `intellichoice-staging-{learning,chat}-api-client-errors`: `StateValue=OK`, `Threshold=0.0`, `GreaterThanThreshold`, `Period=900`, `EvaluationPeriods=1`, `TreatMissingData=notBreaching`, `AlarmActions=[arn:aws:sns:us-east-1:3205…:intellichoice-staging-alerts]` — the **page** topic, exactly as D-419's inventory says. `ClientErrors` Sum over 14 days: learning-api 4 datapoints / total 0; chat-api 4 datapoints / total 0.
- **Evidence source**: `aws logs describe-metric-filters --log-group-name /ecs/intellichoice-staging-learning-api` (and `-chat-api`) / `aws cloudwatch describe-alarms --alarm-names intellichoice-staging-learning-api-client-errors intellichoice-staging-chat-api-client-errors`
- **Observed at**: 2026-08-20T00:04:59Z / 00:04:06Z (LANE-B)
- **Limitations**: only four `ClientErrors` datapoints exist in 14 days despite `default_value = 0` — that indicates the app log groups received very few matching-shaped JSON lines, not that the filter is broken. Confirming that a real crash flows end to end needs a synthetic `client_error` post → 3B-2.
- **Classification**: DEPLOYED_CONFIRMED

#### COST-18 — do the nightly `*_job_complete` records reach CloudWatch?

- **Claim ID**: COST-18
- **Previous repository-side classification**: CONFIRMED_IN_REPOSITORY — DRIFT-87
- **Intended state**: the four `nightly_jobs` filters match the emitted `*_job_complete` records, so `JobCompletions` carries a series and the heartbeat alarms can reach OK.
- **Repository-configured state**: filter `nightly_jobs`, `for_each = toset(var.nightly_job_events)`, pattern `{ $.event = "<job>_job_complete" }` (`app_events.tf:173`: `pattern = "{ $.event = \"${each.key}_job_complete\" }"` with `each.key` **hyphenated**), `dimensions = { job = "$.job" }`, and deliberately **no `default_value`** (the comment at `app_events.tf:190-200` explains CloudWatch rejects `dimensions` + `default_value` together, and that the absence is load-bearing).
- **Observed deployed state**: **all four filters exist** on `/ecs/intellichoice-staging-ops-task` — `intellichoice-staging-job-{session-consolidate,chat-purge,retention-purge,memory-consolidate}`, each pattern verbatim **`{ $.event = "session-consolidate_job_complete" }`** (and the other three, all **HYPHENATED**) → `IntelliChoice/intellichoice-staging/pipeline / JobCompletions`, `value=1`, `default=ABSENT`, `dims={"job":"$.job"}`. The metric they feed **has never published**: `list-metrics` for that namespace returns **7** metrics (`CurriculumTemplates{Created,Retired,Updated}`, `Pipeline{Cost,Filled,Rejected,StoppedEarly}`) and **`JobCompletions` is not among them**; `get-metric-statistics` over 14 days returns **0 datapoints for all four `job` dimensions**. The emitting side (orchestrator-verified): `packages/observability/src/intellichoice_observability/scheduled_jobs.py:61` emits `f"{job.replace('-', '_')}_job_complete"` → `session_consolidate_job_complete`, **UNDERSCORED**. The two can never match. The jobs nevertheless **do run**: `/ecs/intellichoice-staging-ops-task` log streams exist at **18:01 / 18:11 / 18:50 UTC on both 2026-08-18 and 2026-08-19** (stream **metadata** only). The ops-task group holds only 131,813 bytes at 14-day retention, and the other 7 ops-task filters (`curriculum-*`, `pipeline-*`) **do** carry data — so the structured-record path works in general; what is missing is specific to the nightly line.
- **Evidence source**: `aws logs describe-metric-filters --log-group-name /ecs/intellichoice-staging-ops-task` / `aws cloudwatch list-metrics --namespace IntelliChoice/intellichoice-staging/pipeline` / `aws cloudwatch get-metric-statistics --namespace IntelliChoice/intellichoice-staging/pipeline --metric-name JobCompletions --dimensions Name=job,Value=<job> --start-time <-14d> --end-time <now> --period 86400 --statistics Sum` (×4) / `aws logs describe-log-streams --log-group-name /ecs/intellichoice-staging-ops-task --order-by LastEventTime --descending`
- **Observed at**: 2026-08-20T00:04:59Z / 00:05:41Z / 00:06:02Z (LANE-B); stream metadata orchestrator-verified in the same window
- **Limitations**: **no Logs Insights query was run** (no lane may read log content), so job **success** remains unproven — the streams could hold tracebacks. Stream existence proves invocation at the metadata level only. `list-metrics` surfaces metrics with a datapoint in the trailing ~2 weeks, so "absent" is a 14-day statement.
- **Classification**: NOT_PRESENT_IN_DEPLOYED_STATE (the metric series) — **(orchestrator-verified)**; root cause and consequences in `DEPLOYED_INFRA_DRIFT_REGISTER` RD-01 (HIGH)

#### COST-19 — the four nightly heartbeat alarms and their live state

- **Claim ID**: COST-19
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (config-parsing half)
- **Intended state**: four heartbeat alarms with `TreatMissingData: breaching`, `Period: 172800`, `Threshold: 1`, a `job` dimension, routed to the page topic.
- **Repository-configured state**: `nightly_job_heartbeat`, `for_each = toset(var.nightly_job_events)`, `period = 172800`, `threshold = 1`, `statistic = "Sum"`, `LessThanThreshold`, `treat_missing_data = "breaching"`, `dimensions = { job = each.key }`, `alarm_actions = [aws_sns_topic.alerts.arn]` (`modules/observability/app_events.tf:202-231`); staging passes exactly four names (`main.tf:777-782`), `youtube-sync` excluded.
- **Observed deployed state**: **all four exist, every configured attribute matches, and all four are in `ALARM`.** `…-job-chat-purge-heartbeat` ALARM since 2026-08-16T23:15:15Z; `…-job-memory-consolidate-heartbeat` 2026-08-16T23:27:54Z; `…-job-retention-purge-heartbeat` 2026-08-17T00:04:18Z; `…-job-session-consolidate-heartbeat` 2026-08-16T23:49:48Z. All: `tmd breaching`, `Period 172800`, `Threshold 1.0`, `ev 1`, `Statistic Sum`, `Namespace IntelliChoice/intellichoice-staging/pipeline`, `Dimensions job=<job>`, `AlarmActions` and `OKActions` both the **page** topic, `InsufficientDataActions []`. `StateReason` is identical and verbatim on all four: `"Threshold Crossed: no datapoints were received for 1 period and 1 missing datapoint was treated as [Breaching]."` `describe-alarm-history` shows **exactly ONE state transition each, ever** — `INSUFFICIENT_DATA → ALARM` on the timestamps above. **No heartbeat alarm has ever been in `OK`.**
- **Evidence source**: `aws cloudwatch describe-alarms --alarm-name-prefix intellichoice-staging-job- --output json` / `aws cloudwatch describe-alarm-history --alarm-name intellichoice-staging-job-<job>-heartbeat --history-item-type StateUpdate --max-records 20` (×4)
- **Observed at**: 2026-08-20T00:04:35Z / 00:04:45Z (LANE-B)
- **Limitations**: with no `default_value` on the feeding filter (by design), ALARM is ambiguous between "job failed", "job ran but emitted no structured record", and "job never ran". COST-18 narrows it decisively and the answer is worse than any of the three: the filter pattern and the emitted event name **can never match**, so this instrument cannot distinguish a dead job from a healthy one in either direction. The alarms route to a confirmed mailbox, so four alarm emails per state change have been delivered since 2026-08-16.
- **Classification**: DEPLOYED_CONFIRMED as configuration; the runtime state is RD-01's evidence — cross-reference `DEPLOYED_INFRA_DRIFT_REGISTER` RD-01

#### COST-21 — enumerate every alarm; is any alarm on a product-KPI metric?

- **Claim ID**: COST-21 (with P1-10)
- **Previous repository-side classification**: CONFIRMED_IN_REPOSITORY, MEDIUM drift
- **Intended state**: `sessions_completed_floor` is the only product-KPI alarm and its double guard means zero such alarms can be instantiated; `qa_answers_total` has no alarm at all.
- **Repository-configured state**: `sessions_completed_floor` with `count = var.daily_completed_sessions_floor > 0 ? 1 : 0` (`modules/observability/app_events.tf:130-131`); staging sets the variable to `0` explicitly (`environments/staging/main.tf:787`). No alarm resource anywhere references `qa_answers_total`.
- **Observed deployed state**: the full unfiltered enumeration returned **`MetricAlarms = 34`, `CompositeAlarms = 0`, no `NextToken`** (single page). Prefix query for `intellichoice-staging-learning-sessions-completed-floor` → **`{"MetricAlarms":0,"CompositeAlarms":0}` — absent, as predicted.** All four `describe-alarms-for-metric` calls (both namespaces × `learning_sessions_completed_total`, `qa_answers_total`) → `{"MetricAlarms":0}`. A name/metric regex over the dump for `session|completed|qa_answer` hits only `intellichoice-staging-job-session-consolidate-heartbeat`, matched on the word "session" in a *job* name (its metric is `JobCompletions`, an ops metric). **Product-KPI alarm count deployed = 0.** The 34 break down as: ALB 6, ECS/ContainerInsights 4, RDS 6, metric-math 2, custom-namespace **app plumbing** 12 (Bedrock call/circuit/cost, ClientErrors, BackgroundTaskFailures, LangSmithIngestFailed × 2 services), custom-namespace **pipeline ops** 4 (JobCompletions heartbeats) — none of the 12 is a product KPI. **Meanwhile both KPI metrics carry live data:** `learning_sessions_completed_total` 11 datapoints / Sum 8 over 30 days, and `qa_answers_total{result=grounded}` 9 datapoints / Sum 409 over 30 days. The KPIs are being bridged; nothing alarms on them, so a floor would be meaningful today.
- **Evidence source**: `aws cloudwatch describe-alarms --max-records 100` (unfiltered, paginated to exhaustion) / `aws cloudwatch describe-alarms --alarm-name-prefix intellichoice-staging-learning-sessions-completed-floor` / `aws cloudwatch describe-alarms-for-metric --namespace IntelliChoice/intellichoice-staging/{learning-api,chat-api} --metric-name {learning_sessions_completed_total,qa_answers_total}` / `aws cloudwatch list-metrics --namespace IntelliChoice/intellichoice-staging/{learning-api,chat-api}` / `aws cloudwatch get-metric-statistics` (30-day Sums)
- **Observed at**: 2026-08-20T00:04:06Z / 00:04:30Z (LANE-B)
- **Limitations**: `describe-alarms-for-metric` answers only for the exact namespace/metric/dimension triple queried — the unfiltered 34-row enumeration is the authoritative negative. This falsifies `AUDIT_2026_08_16`'s "four new application alarms reading OK" **if** that sentence meant product-KPI alarms; it is consistent if it meant the four `client-errors`/`background-failures` instances, which do exist and do read OK.
- **Classification**: DEPLOYED_CONFIRMED (the config's double guard holds live; runtime-proven — see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-07)

#### COST-23 — two SNS topics, subscription state, and the deployed D-401 split

- **Claim ID**: COST-23
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (config-parsing half)
- **Intended state**: two topics with one confirmed subscription each; the informational alarms route to `alerts-info` and everything else to `alerts`, with no alarm carrying both.
- **Repository-configured state**: `aws_sns_topic.alerts` (`modules/observability/main.tf:45`) + `alerts_email` (`:50`); `aws_sns_topic.alerts_info` (`:61`) + `alerts_info_email` (`:66`). The info endpoint is `coalesce(var.informational_notification_email, var.notification_email)` with the informational variable defaulting to `null` and **no setter in the repo** — so topic-level routing splits while the mailbox stays one address.
- **Observed deployed state**: **exactly two topics in the whole account**, `arn:aws:sns:us-east-1:3205…:intellichoice-staging-alerts` and `…-alerts-info`. Each: `SubscriptionsConfirmed 1`, **`SubscriptionsPending 0`**, `SubscriptionsDeleted 0`, `KmsMasterKeyId NONE`. Both subscriptions `email` → **`k***@gmail.com`**, both **CONFIRMED** (real subscription ARNs, not the literal `PendingConfirmation`). `aws sns list-subscriptions` account-wide returns exactly these two. Alarm→topic grouping from the 34-row dump: **26** alarms → `alerts` (page), **4** → `alerts-info`, **4** → Application-Auto-Scaling policy ARNs. **No alarm carries both topic ARNs**, and every SNS-routed alarm's `OKActions` equals its `AlarmActions`. The four `alerts-info` members are exactly `{learning,chat}-api-capacity-above-floor` and `{learning,chat}-api-langsmith-ingest-failed`, with `sessions-completed-floor` absent — precisely the configured `_INFORMATIONAL` set minus its count-gated third member.
- **Evidence source**: `aws sns list-topics` / `aws sns get-topic-attributes --topic-arn arn:aws:sns:us-east-1:3205…:intellichoice-staging-{alerts,alerts-info}` / `aws sns list-subscriptions-by-topic --topic-arn <each>` / `aws sns list-subscriptions` / the `describe-alarms` dump grouped by `AlarmActions`
- **Observed at**: 2026-08-20T00:05:15Z / 00:04:06Z (LANE-B)
- **Limitations**: subscription state was **read** only — confirming a pending subscription is a user-side mutation and was not attempted (none was pending). `get-subscription-attributes` was not called: it answers nothing once both are confirmed. Both topics are unencrypted (`KmsMasterKeyId: NONE`), and the confirmed endpoint is a `gmail.com` address rather than an `intellichoice.org` one — recorded, not judged.
- **Classification**: DEPLOYED_CONFIRMED (resolves the audit-era `PendingConfirmation` observation)

#### COST-24 — the eight `alarms.tf` alarms from the alerting side

- **Claim ID**: COST-24
- **Previous repository-side classification**: CONFIRMED → LOCALLY_VERIFIED (config-parsing half) — named by F-03
- **Intended state**: the same eight alarms as SEC-10, at the right cardinality and with the configured thresholds and periods.
- **Repository-configured state**: eight blocks in `modules/observability/alarms.tf:29-238`; three executed pytest tests in `packages/observability/tests/test_alarm_severity_routing.py` assert the **configuration** — which F-03 notes upgrades it from "file read by an auditor" to "file asserted by an executed test", and still says nothing about AWS.
- **Observed deployed state**: all eight blocks deployed at ×2 = **16 instances**, every one `OK`, with `Threshold`, `Period`, `EvaluationPeriods`, `ComparisonOperator`, `TreatMissingData` and `Namespace` matching config on every instance the dump allowed comparing (values enumerated under SEC-10, including the per-engine `rds_connections` split 80.0/40.0 and `ecs_memory` 716.0 MiB). Every alarm in the account has `ActionsEnabled: true` — no alarm is silenced. No alarm is in `INSUFFICIENT_DATA` (`--state-value INSUFFICIENT_DATA` → empty).
- **Evidence source**: `aws cloudwatch describe-alarms --max-records 100 --output json` (the single shared dump) / `aws cloudwatch describe-alarms --state-value ALARM` / `--state-value INSUFFICIENT_DATA` / `--alarm-types CompositeAlarm`
- **Observed at**: 2026-08-20T00:04:06Z (LANE-B)
- **Limitations**: this compares alarm **attributes**, not alarm **efficacy** — an alarm can match config exactly and still be unable to fire, which is what COST-18/COST-19 demonstrate for the heartbeat family. `AlarmDescription` text was not diffed. The executed config test remains config-only evidence; it does not and cannot assert deployed state.
- **Classification**: DEPLOYED_CONFIRMED

#### COST-25 — deployed alarm count vs configured count

- **Claim ID**: COST-25
- **Previous repository-side classification**: CONFIRMED_IN_REPOSITORY
- **Intended state**: the claim's own point is that the configured and deployed alarm counts are *not* the same number.
- **Repository-configured state**: **15** `aws_cloudwatch_metric_alarm` resource blocks (`modules/observability/main.tf:132,208,231`; `alarms.tf:29,56,87,115,136,163,187,213`; `app_events.tf:45,96,130,202`). Recounted at staging cardinality from the module call at `environments/staging/main.tf:750-800` (`services` 2, `log_group_names` 2, `capacity_floors` 2, `database_instances` 2, `nightly_job_events` 4, `daily_completed_sessions_floor` 0): 2+2+2+2+2+2+2+2+2+2+2+2+2+**0**+4 = **30 configured instances**.
- **Observed deployed state**: **34 alarms total = 30 observability-module instances + 4 created by Application Auto Scaling** (rows 11/12/27/28, whose `AlarmActions` are policy ARNs rather than SNS topics). `CompositeAlarms: 0`. Reconciliation: **configured module instances 30, deployed module instances 30, per-name delta 0** — not a single configured instance is missing, and not a single deployed alarm is unaccounted for by the config. The honest headline is the three-number chain: **15 resource blocks → 30 module instances deployed → 34 alarms in the account.**
- **Evidence source**: `aws cloudwatch describe-alarms --max-records 100` (paginated to exhaustion; single page) / `aws cloudwatch describe-alarms --alarm-types CompositeAlarm` / the four AAS-actioned alarms identified from the same dump (their `describe-scaling-policies` counterpart is LANE-A's ARCH-11)
- **Observed at**: 2026-08-20T00:04:06Z (LANE-B)
- **Limitations**: this is an alarm-**existence** count; threshold agreement is COST-24's subject. The test file's warning (`packages/observability/tests/test_alarm_severity_routing.py:36-39`, "the deployed alarm count and the configured one are not the same number") is correct about **resource blocks vs deployed instances** (15 vs 34) but the **instance-level** counts agree exactly once `sessions_completed_floor`'s zero count and the four AAS alarms are handled. Separately: 34 deployed alarms sit past the 10-alarm always-free limit, so 24 are billable (see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-10).
- **Classification**: DEPLOYED_CONFIRMED (deployed 30 == configured 30, delta 0)

#### COST-26 — live SNS subscription state, including any PendingConfirmation

- **Claim ID**: COST-26
- **Previous repository-side classification**: deferred to 3B, §4.1 — DRIFT-89
- **Intended state**: the live subscription state, and whether a second informational endpoint exists.
- **Repository-configured state**: none recorded — §9's line is "live SNS subscription state (user-side)"; 3A produced no block. COST-23's block notes the info endpoint coalesces to the single address by default.
- **Observed deployed state**: both topics report `SubscriptionsConfirmed: 1` and **`SubscriptionsPending: 0`**; both subscriptions are `email` → `k***@gmail.com` with real subscription ARNs (`…:4319e214-d047-492b-a4d3-0300aadbeddc` on `alerts`, `…:89fe91a9-0c19-497d-9c11-70b0527fc489` on `alerts-info`). `aws sns list-subscriptions` account-wide returns exactly these two, so **no subscription anywhere in the account is in `PendingConfirmation`**. The informational endpoint is the **same single address** as the page endpoint — exactly what the `coalesce(...)` default predicts: routing is split at the topic, the mailbox is still one.
- **Evidence source**: `aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:us-east-1:3205…:intellichoice-staging-alerts` (and `…-alerts-info`) / `aws sns list-subscriptions` / `aws sns get-topic-attributes --topic-arn <each>`
- **Observed at**: 2026-08-20T00:05:15Z (LANE-B)
- **Limitations**: reading only. Confirming a subscription is a user-side mutation and was not attempted. This resolves the audit-era `PendingConfirmation` observation as no longer true; it says nothing about whether delivered mail is being read.
- **Classification**: DEPLOYED_CONFIRMED

#### COST-27 — the `LangSmithIngestFailed` filter and alarm, routed to `alerts-info`

- **Claim ID**: COST-27
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (masking half)
- **Intended state**: filter and per-service alarm (threshold 10 over 900 s) deployed, routed to the informational channel rather than the page channel.
- **Repository-configured state**: filter and alarm both `for_each = var.log_group_names`, pattern keyed on `$.logger = "langsmith.client"`, routed to `aws_sns_topic.alerts_info` deliberately (`modules/observability/alarms.tf:56-84`, action at `:80-81`). `HIDE_INPUTS`/`HIDE_OUTPUTS` are client-side flags; the repo cannot show what the SaaS received.
- **Observed deployed state**: filters present on **both** app log groups — `…-langsmith-ingest-failed`, pattern **`{ $.logger = "langsmith.client" }`** → `LangSmithIngestFailed`, `value=1`, `default=0.0`, `unit=Count`. Alarms present on both: `Threshold=10.0 GT`, `Period=900`, `EvaluationPeriods=2`, `AlarmActions` and `OKActions` both `[…:intellichoice-staging-alerts-info]` — **not the page channel**. Current state `OK` on both. `StateReason` (chat-api): `"Threshold Crossed: 1 datapoint [10.0 (18/08/26 22:08:00)] was not greater than the threshold (10.0)."` **The signal is live and large:** 14-day Sums learning-api **2800**, chat-api **1441**; daily series zero on 08-09…08-14, then 2252/1153 on 08-15, 524/239 on 08-16, 0/44 on 08-17, 24/5 on 08-18. Alarm history shows **10 state transitions each in ~2 days** (learning-api flipped OK→ALARM→OK five times between 2026-08-17T03:02Z and 23:12Z).
- **Evidence source**: `aws logs describe-metric-filters --log-group-name /ecs/intellichoice-staging-{learning,chat}-api` / `aws cloudwatch describe-alarms --max-records 100` (filtered to `MetricName==LangSmithIngestFailed`) / `aws cloudwatch get-metric-statistics --namespace IntelliChoice/intellichoice-staging/<svc> --metric-name LangSmithIngestFailed --start-time <-14d> --end-time <now> --period 86400 --statistics Sum` / `aws cloudwatch describe-alarm-history --alarm-name intellichoice-staging-<svc>-langsmith-ingest-failed --history-item-type StateUpdate --max-records 10`
- **Observed at**: 2026-08-20T00:04:59Z / 00:06:02Z / 00:08:12Z (LANE-B)
- **Limitations**: what LangSmith actually received is external (SEC-23, §3). Whether these failures are 403s, quota rejections or timeouts needs log content, which no lane may read. The D-401 comment predicted this alarm would "sit in ALARM indefinitely"; deployed it **flaps** instead, and every flap lands in the quiet channel — which is what the split was built for, and also why nobody is paged. See `DEPLOYED_INFRA_DRIFT_REGISTER` RD-04.
- **Classification**: DEPLOYED_CONFIRMED (configuration half; the live failure volume is a new runtime observation)

#### COST-28 — does a NAT exist, is it billing while idle, and is the ~$33/mo figure right?

- **Claim ID**: COST-28
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED
- **Intended state**: the consumer-keyed gate produces one NAT under defaults, at roughly $33/mo.
- **Repository-configured state**: `private_egress_consumers` map + `anytrue(...)` → `nat_gateway_enabled` (`environments/staging/main.tf:115-136`); `modules/scheduled-jobs/main.tf:121-125` cross-references the same map; X-Ray rides a VPC endpoint, so LangSmith is the only general-internet consumer. The "~$33/mo" figure is a repo comment at `modules/vpc/main.tf:170`.
- **Observed deployed state**: **the NAT is carrying real traffic — it is not idle.** Daily Sums over the 30-day window (first datapoint is the NAT's first full day): BytesOut/BytesIn/ActiveConnections — 08-06 773,390/532,975/495; 08-07 905,055/581,993/439; 08-08 140,040/115,806/115; 08-09 116,008/93,880/81; 08-10 876,926/414,528/312; 08-11 726,513/322,309/207; 08-12 1,182,166/557,387/256; 08-13 4,695,730/2,257,927/913; 08-14 3,424,820/1,790,565/640; 08-15 **10,212,576**/4,506,376/**1,865**; 08-16 2,169,254/1,190,070/864; 08-17 106,230/61,321/30; 08-18 99,307/64,717/40; **08-19 0/0/0**. Total ≈ **26.4 MB out / 12.5 MB in over 14 days** — a small, bursty, development-shaped trickle. **Cost, measured:** `USAGE_TYPE = NatGateway-Hours` → UsageQuantity **290 hours** (12.08 days), and by `RECORD_TYPE` **`Usage +$13.0515843485` fully offset by `Credit -$13.0515843499`**; `NatGateway-Bytes` `UnblendedCost -0.0000000014`. $13.0516 / 12.08 days = **$1.080/day ≈ $32.9 per 30.4-day month** — the repo's "~$33/mo" is accurate to within rounding, now measured. **Net cash cost of the NAT to date: $0.00**, absorbed by credits. The 0-byte day on 2026-08-19 shows the hourly charge continues with no egress at all.
- **Evidence source**: `aws cloudwatch get-metric-statistics --namespace AWS/NATGateway --metric-name BytesOutToDestination --dimensions Name=NatGatewayId,Value=nat-07ab02d5cd28b6f72 --start-time 2026-07-21T00:04:49Z --end-time 2026-08-20T00:04:49Z --period 86400 --statistics Sum` (and `BytesInFromDestination`, `ActiveConnectionCount`) / `aws ce get-cost-and-usage --time-period Start=2026-08-01,End=2026-08-20 --granularity MONTHLY --metrics UnblendedCost UsageQuantity --group-by Type=DIMENSION,Key=RECORD_TYPE --filter '{"Dimensions":{"Key":"USAGE_TYPE","Values":["NatGateway-Hours","NatGateway-Bytes"]}}'`
- **Observed at**: 2026-08-20T00:04:49Z (traffic) / 00:12Z (cost) — LANE-C
- **Limitations**: `BytesOutToDestination` does not identify the destination, so attributing this traffic to LangSmith is an **inference** — supported by ARCH-07 removing the other candidate consumer and by the six VPC endpoints removing AWS-API traffic. Confirming it would need VPC Flow Logs, which are not enabled as far as this lane observed. The queue's suggested `USAGE_TYPE_GROUP = "EC2: NAT Gateway-Hours"` filter returned all zeros — that group name does not match this account's data; the working dimension is `USAGE_TYPE`. Month-to-date is flagged `Estimated: true`, and credit balance/expiry are not exposed, so *when* the ~$33/mo becomes visible in net spend cannot be predicted (see RD-03).
- **Classification**: DEPLOYED_CONFIRMED (against config defaults; ~$33/mo confirmed as a list-price run rate, net $0.00 today)

#### COST-29 — live task cpu/memory and task counts per service

- **Claim ID**: COST-29
- **Previous repository-side classification**: PARTIALLY_IMPLEMENTED, MEDIUM drift → LOCALLY_VERIFIED (config half)
- **Intended state**: learning-api 512/1024 × 2 and chat-api 256/512 × 1 — the asymmetry that makes the D-136 price table's per-task columns (measured at 256 CPU) understate current capacity.
- **Repository-configured state**: learning-api `cpu = 512` / `memory = 1024` (`environments/staging/main.tf:430-431`, AUD-F-28/D-122 rationale at `:422-429`), `desired_count = 2` (`:446`), floor 2 (`:447`, `:828`); chat-api on module defaults 256/512 (`modules/ecs-service/variables.tf:56`, `:62`), desired 1, floor 1 (`main.tf:832`). `docs/ARCHITECTURE.md:254-283` quotes the D-136 table as current without the resize caveat the terraform carries.
- **Observed deployed state**: learning-api `:150` task `cpu 512` / `memory 1024`, desired 2 / running 2, both live tasks reporting `cpu: "512"`, `memory: "1024"`; chat-api `:148` task `cpu 256` / `memory 512`, desired 1 / running 1, live task `cpu: "256"`, `memory: "512"`; ops-task `:144` `256`/`512`, scheduler-invoked, 0 running. Task start times: learning-api 2026-08-18T18:47:17Z (`us-east-1a`) and 18:47:35Z (`us-east-1b`); chat-api 2026-08-18T22:10:50Z (`us-east-1b`). Total live Fargate footprint at this instant: **3 tasks, 1,280 CPU units, 2,560 MiB** — the sidecar's 128/256 per task is *inside* those figures, not additional.
- **Evidence source**: `aws ecs describe-task-definition --task-definition intellichoice-staging-learning-api:150 --query 'taskDefinition.[family,revision,cpu,memory]'` (and `chat-api:148`) / `aws ecs describe-services --cluster intellichoice-staging --services … --query 'services[].[serviceName,desiredCount,runningCount,taskDefinition]'` / `aws ecs describe-tasks --cluster intellichoice-staging --tasks <3 arns> --query 'tasks[].[taskDefinitionArn,cpu,memory,lastStatus,startedAt]'`
- **Observed at**: 2026-08-20T00:03Z–00:04Z (LANE-A)
- **Limitations**: this is **provisioned size, not utilisation** — nothing here says whether the 512 units are used. chat-api's single task is a snapshot: scaling activities show it at 3 tasks on 2026-08-18T22:10Z and 2026-08-17T06:19Z, so any monthly cost figure derived from "1 task" understates it; the honest cost-model input is the 1–3 band plus the scaling history, not the instantaneous count.
- **Classification**: DEPLOYED_CONFIRMED

### 2.4 REQ family (2)

#### REQ-18 — is schema-invalid capture enabled in the deployed stack?

- **Claim ID**: REQ-18
- **Previous repository-side classification**: deferred to 3B, §4.1
- **Intended state**: the documented schema-invalid rate would have a live source in the deployed stack.
- **Repository-configured state**: **none** — §9's evidence line is "schema-invalid rate; is capture enabled now", and 3A produced no block. The repository configures no capture either, so deployed absence and repo absence agree.
- **Observed deployed state**: **no schema-invalid metric filter exists on any of the five log groups.** The complete filter inventory is 7 per app group (`background-failures`, `bedrock-call-failed`, `bedrock-circuit-open`, `bedrock-cost-cents`, `bedrock-duration-ms`, `client-errors`, `langsmith-ingest-failed`), 11 on `ops-task` (4 job + 3 curriculum + 4 pipeline), and **0** on both `/emf` groups — nothing matching `schema`, `invalid`, `repair` or `validation`. An env-var **name** scan on both task definitions for `SCHEMA|INVALID|CAPTURE|REPAIR|SAMPLE` returned **`NONE-MATCHED`** on both. No `schema_invalid`-shaped metric appears in either app namespace's `list-metrics` output (35 and 28 metrics respectively).
- **Evidence source**: `aws logs describe-metric-filters --log-group-name /ecs/intellichoice-staging-{learning-api,chat-api,ops-task,learning-api/emf,chat-api/emf}` / `aws ecs describe-task-definition --task-definition intellichoice-staging-{learning,chat}-api --query 'taskDefinition.containerDefinitions[0].environment[].name'` / `aws cloudwatch list-metrics --namespace IntelliChoice/intellichoice-staging/{learning-api,chat-api}`
- **Observed at**: 2026-08-20T00:04:59Z / 00:07:18Z / 00:05:41Z (LANE-B)
- **Limitations**: **no Logs Insights query was run**, so this cannot say whether the applications *emit* `schema_invalid` lines that simply have no filter over them — which is the likely state given the SPEC's repair-retry design. What is proven is the absence of **CloudWatch-side capture**, not the absence of the underlying event. Re-measuring the rate needs log content or a local run (3B-2).
- **Classification**: NOT_PRESENT_IN_DEPLOYED_STATE — and the repository configures none of it either, so **deployed matches repo**; the intent gap is the existing 3A entry's subject, cross-referenced rather than re-raised (no new drift entry)

#### REQ-50 — is SLO instrumentation deployed, and was 100 concurrent ever demonstrated?

- **Claim ID**: REQ-50
- **Previous repository-side classification**: deferred to 3B, §4.1
- **Intended state**: (a) p95 latency alarms, `http_requests_total` metrics and a dashboard exist in the deployed stack; (b) 100 concurrent users were demonstrated.
- **Repository-configured state**: none recorded for the claim; the configured side observed here is `target_latency_p95` (`modules/observability/main.tf:231-252`) with per-service thresholds via `latency_p95_alarm_thresholds` (`:240`).
- **Observed deployed state**: **(a) deployed.** Four p95 alarms, all using `ExtendedStatistic: p95`: `…-learning-api-p95-latency` 3.0 s OK (period 60, ev 3); `…-chat-api-p95-latency` **20.0 s** OK (60, 3); `…-learning-api-p95-latency-scale-out` 3.0 s OK (60, 2); `…-chat-api-p95-latency-scale-out` 3.0 s OK (60, 2). `http_requests_total` exists and carries data, dimensioned by `status` — learning-api 9 dimensions (`200,204,400,401,403,404,409,422,503`), chat-api 6 (`200,202,401,403,404,422`); `http_request_duration_seconds` exists on both. One dashboard, `intellichoice-staging-overview`, LastModified 2026-08-10T05:41:04Z, 9,771 bytes, **19 widgets** (14 metric, 3 text, 2 log). Custom-metric inventory with data: learning-api **35**, chat-api **28**, pipeline **7** — **63 app metrics carry data while only 12 have alarms**. **(b) never demonstrated.** 30-day hourly `RequestCount`: 671 hours with data, **78,699 requests total**, peak hour 2026-07-30T18:05:00Z = **10,850 requests** (≈3.0 req/s). Last 24 h per-minute: 1,440 buckets, busiest minute 2026-08-19T22:15:00Z = **51 requests** (≈0.85 req/s). `ActiveConnectionCount` Maximum over 4 days at 5-min resolution: 824 buckets, **peak 0.0**.
- **Evidence source**: `aws cloudwatch describe-alarms --output json` (filtered to `MetricName=="TargetResponseTime"`) / `aws cloudwatch list-dashboards` + `aws cloudwatch get-dashboard --dashboard-name intellichoice-staging-overview` / `aws cloudwatch list-metrics --namespace IntelliChoice/intellichoice-staging/{learning-api,chat-api,pipeline}` / `aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB --metric-name RequestCount --dimensions Name=LoadBalancer,Value=app/intellichoice-staging-alb/a1e99fb6d592d3d4 --start-time <-30d> --end-time <now> --period 3600 --statistics Sum` (and the 1-day/60 s and `ActiveConnectionCount` variants)
- **Observed at**: 2026-08-20T00:05:19Z / 00:06:31Z / 00:07:11Z–00:07:56Z (LANE-B)
- **Limitations**: dashboard **existence and widget count** were confirmed; widget metric queries were read only far enough to extract titles, so no widget was proven to resolve. Request rate is not concurrency, and CloudWatch's 1,440-datapoint ceiling forced a 30-day hourly window rather than 90-day (the 90-day daily read showed the same magnitude, highest day ~4,149). An `ActiveConnectionCount` Maximum of 0.0 across 824 buckets is itself odd — either the metric is not emitted for this ALB or connections are too short to sample; the number is recorded, not interpreted. *Producing* 100 concurrent users is a load run → 3B-2, so capacity remains a load-test-era extrapolation.
- **Classification**: DEPLOYED_STATE_PARTIALLY_CONFIRMED — (a) DEPLOYED_CONFIRMED; (b) DEPLOYED_STATE_PARTIALLY_CONFIRMED (LOW note, no new drift entry)

### 2.5 TEST family (1)

#### TEST-09 — CloudTrail on, GuardDuty genuinely absent

- **Claim ID**: TEST-09
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (repo half)
- **Intended state**: T-01's two opposite answers — CloudTrail logging, GuardDuty absent from the **account** rather than merely from terraform.
- **Repository-configured state**: CloudTrail wired at `environments/staging/main.tf:743-748`; **no `aws_guardduty_*` resource anywhere**, deliberate and annotated (D-125, the same always-on-cost argument as D-087's WAF deferral).
- **Observed deployed state**: CloudTrail `IsLogging: true` (full status under SEC-16, delivery ~90 s fresh). GuardDuty: **`{"DetectorIds": []}`** — empty. WAF: `{"WebACLs": []}` on `--scope REGIONAL` **and** `{"WebACLs": []}` on `--scope CLOUDFRONT`. So GuardDuty's absence is a real property of the account — nobody enabled it out of band — and the D-087 WAF companion deferral is confirmed in the same pass.
- **Evidence source**: `aws cloudtrail get-trail-status --name intellichoice-staging-trail` / `aws guardduty list-detectors` / `aws wafv2 list-web-acls --scope REGIONAL` / `aws wafv2 list-web-acls --scope CLOUDFRONT`
- **Observed at**: 2026-08-20T00:07:28Z (LANE-C)
- **Limitations**: `list-detectors` is **regional** — only `us-east-1` was checked, so a detector in another region would not appear. Given the multi-region trail shows all activity is us-east-1-based and the account is single-environment, the residual risk is low, but this is an inference rather than a measurement.
- **Classification**: DEPLOYED_CONFIRMED

### 2.6 WORK family (5)

#### WORK-02 — live SNS subscription state (the user-side half)

- **Claim ID**: WORK-02
- **Previous repository-side classification**: deferred to 3B, §4.1 — DRIFT-89
- **Intended state**: the same live SNS read as COST-26 — per-topic subscription state including any PendingConfirmation, and whether a second endpoint exists.
- **Repository-configured state**: none — §9's line is "live SNS subscription state (user-side)"; no 3A block. Two topics with one email subscription each are configured (`modules/observability/main.tf:45/50/61/66`).
- **Observed deployed state**: two topics, `intellichoice-staging-alerts` and `intellichoice-staging-alerts-info`, each `SubscriptionsConfirmed: 1` / `SubscriptionsPending: 0` / `SubscriptionsDeleted: 0`, `KmsMasterKeyId: NONE`. Both endpoints are the **same** address, `k***@gmail.com`, protocol `email`, both **CONFIRMED**. Account-wide `list-subscriptions` returns exactly those two — **nothing pending anywhere**. No second informational endpoint exists, consistent with `informational_notification_email` defaulting to `null` with no setter. The page topic carries **26** of the 34 deployed alarms, so "26 alarms to one address" is literally true again *for the page topic specifically*, while the four informational alarms are separable by topic ARN.
- **Evidence source**: `aws sns list-topics` / `aws sns get-topic-attributes --topic-arn <each>` / `aws sns list-subscriptions-by-topic --topic-arn <each>` / `aws sns list-subscriptions`
- **Observed at**: 2026-08-20T00:05:15Z (LANE-B)
- **Limitations**: one command set answered COST-23, COST-26 and WORK-02; the reads are identical and are not counted three times as evidence. Confirming a subscription is a user-side mutation and was not attempted. Both topics are unencrypted — recorded, not judged.
- **Classification**: DEPLOYED_CONFIRMED

#### WORK-06 — what image is live, and is the rollout complete?

- **Claim ID**: WORK-06
- **Previous repository-side classification**: CONFIRMED_IN_REPOSITORY — deploy-state half deferred
- **Intended state**: `gha-44a12dfc9549` (run 32171998780) is live on both services, with exactly one `PRIMARY` deployment per service at `rolloutState: COMPLETED`.
- **Repository-configured state**: the code fix (the global sweep in `chat_turn_cancellation.request()`) is confirmed in code; the deploy facts — run id, image tag, rollout state — are external and were not verified in 3A.
- **Observed deployed state**: **exactly one** deployment per service, `status: PRIMARY`, **`rolloutState: COMPLETED`**, desired == running on both (2/2 and 1/1); deployment `createdAt` 2026-08-18T18:46:28Z (learning) / 18:49:33Z (chat). `gha-44a12dfc9549` is confirmed live **by tag and by digest**: learning-api image `3205….dkr.ecr.us-east-1.amazonaws.com/learning-api:gha-44a12dfc9549`, ECR digest `sha256:eb0b1823cb2221c31764dac17c818cd09a1783f806a4bbb6ba88f0cd54b7d21c` (pushed 2026-08-18T18:38:53Z), and that same digest on both running containers; chat-api `…/chat-api:gha-44a12dfc9549`, digest `sha256:06965774f75cca49cc76ac89b8c518f021c1c2309d1f7df65672c758bf90eba0` (pushed 18:39:51Z), matching on the running container. `ops-task:144` runs the **learning-api** image at the same tag with `command: ["true"]`. All three ECR repositories are `imageTagMutability: IMMUTABLE`, `scanOnPush: true`, `encryptionType: AES256`; the previous tag in both app repos is `gha-df79b290bf65` (2026-08-17); untagged buildx attestation digests sit alongside each tagged one. Service `platformVersion`: learning-api `1.4.0`, chat-api `LATEST` (all running tasks report `1.4.0`).
- **Evidence source**: `aws ecs describe-services --cluster intellichoice-staging --services … --query 'services[].{name:serviceName,deployments:deployments[].{status:status,rolloutState:rolloutState,taskDefinition:taskDefinition,desired:desiredCount,running:runningCount}}'` / `aws ecr describe-images --repository-name learning-api --query 'sort_by(imageDetails,&imagePushedAt)[-5:]'` / `aws ecr describe-images --repository-name chat-api --image-ids imageTag=gha-44a12dfc9549` / `aws ecs describe-tasks --cluster intellichoice-staging --tasks <3 arns>` / `aws ecr describe-repositories`
- **Observed at**: 2026-08-20T00:04Z–00:06Z (LANE-A)
- **Limitations**: the GitHub Actions **run id** itself is GitHub state and was not verified from AWS — only the tag it produced. The behavioural half (`POST …/turns/probe/cancel` answering 202 for an invented session) is an HTTP probe → 3B-2. Rollout COMPLETED means ECS finished the deployment, not that the application is healthy beyond the ALB's `/readyz` check.
- **Classification**: DEPLOYED_CONFIRMED

#### WORK-08 — are D-401 and D-406 applied in AWS, or merely committed?

- **Claim ID**: WORK-08
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (config half) — DRIFT-93
- **Intended state**: `PROGRESS.md:155-156` says D-401/D-406 are **unapplied**; commit `2e301d6` is titled "D-401/D-406 applied". A commit title is a claim of an apply, not the apply. `terraform plan` is forbidden, so the resources themselves must answer.
- **Repository-configured state**: both fully present in config. D-401: `aws_sns_topic.alerts_info` + its email subscription + three alarms routed to it, with an enforcing test whose `_INFORMATIONAL` set (`packages/observability/tests/test_alarm_severity_routing.py:28-40`) is `{langsmith_ingest_failed, capacity_above_floor, sessions_completed_floor}` and an in-file note that the third is "Configured, not deployed". D-406: `local.private_egress_consumers` + `needs_private_egress` driving `nat_gateway_enabled`. Code commits `73e29c6` (D-401) and `15bb6b3` (D-406) predate the disputed date.
- **Observed deployed state**: **both are APPLIED.** D-401 side: the topic `intellichoice-staging-alerts-info` **exists in AWS with a confirmed email subscription** — its existence is the apply — and the deployed `alerts-info` membership is **exactly four alarms**: `intellichoice-staging-{chat,learning}-api-capacity-above-floor` and `intellichoice-staging-{chat,learning}-api-langsmith-ingest-failed`. `intellichoice-staging-learning-sessions-completed-floor` is **absent from AWS entirely**, so `sessions_completed_floor` contributes zero instances — exactly what the test file's own note predicts. The test's non-vacuity control holds live: `target_5xx` (×2), `rds_free_storage` (×2), `bedrock_circuit_open` (×2) and `bedrock_spend_spike` (×2) all carry the **page** ARN and none carries `alerts-info`. D-406 side: **the NAT exists**, `nat-07ab02d5cd28b6f72`, `CreateTime 2026-08-07T04:47:31Z` — 11 days *before* both `15bb6b3` (2026-08-18T07:52:56Z) and `2e301d6` (2026-08-18T20:32:35Z) — with an active `0.0.0.0/0 → nat` route in the private route table and `ManagedBy=terraform`. Independent corroboration that a `terraform apply` ran that day: all three task-definition families registered a new revision within **3 ms** of each other at **2026-08-18T20:20:41Z**. **`PROGRESS.md:155-156`'s "unapplied" is refuted by AWS; ROADMAP was right.**
- **Evidence source**: `aws sns list-topics` / `aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:us-east-1:3205…:intellichoice-staging-alerts-info` / `aws cloudwatch describe-alarms --max-records 100` grouped by `AlarmActions` / `aws cloudwatch describe-alarms --alarm-name-prefix intellichoice-staging-learning-sessions-completed-floor` / `aws ec2 describe-nat-gateways --query 'NatGateways[].[NatGatewayId,State,CreateTime]'` / `aws ec2 describe-route-tables` / `aws ecs list-task-definitions --family-prefix intellichoice-staging-<family> --sort DESC --max-items 5`
- **Observed at**: 2026-08-20T00:04:06Z / 00:05:15Z (LANE-B); 00:04:13Z–00:04:49Z (LANE-C); 00:04Z–00:06Z (LANE-A)
- **Limitations**: the CloudTrail `CreateTopic` / `CreateNatGateway` cross-check that would date the apply against `2e301d6` was **not run** — resource existence already settles applied-vs-unapplied, so it was not needed. `CreateTime` dates the resource, not the commit (see ARCH-29). The registration burst proves *an* apply ran on 2026-08-18, not which configuration it carried.
- **Classification**: DEPLOYED_CONFIRMED — D-401 and D-406 are applied; the documentation, not the config, was wrong (see `DEPLOYED_INFRA_DRIFT_REGISTER` RD-05)

#### WORK-23 — is any deletion job present as a deployed schedule?

- **Claim ID**: WORK-23
- **Previous repository-side classification**: deferred to 3B, §4.1
- **Intended state**: `ARCHITECTURE.md:31-36` — "That retention job stays **unscheduled** until this one has a record of firing." So the correct deployed state is absence.
- **Repository-configured state**: `checkpoint_retention_cli.py` exists with a manual `Makefile:106` target and its own tests but is deliberately **not** in `locals.jobs`; `grep -i checkpoint` over `terraform/` returns only comments (`modules/scheduled-jobs/main.tf:46`) and dashboard metric names — no `aws_scheduler_schedule` resource for it anywhere.
- **Observed deployed state**: **no `checkpoint-retention` schedule exists.** The complete schedule list is the five names under ARCH-04; none contains "checkpoint", and none is a deletion job beyond the two already-enabled purges. EventBridge **Rules** hold exactly one entry, and it is not a cron: `intellichoice-staging-ops-task-failed`, `State: ENABLED`, `EventBusName: default`, description "Any ops-task container that stops with a non-zero exit code.", `EventPattern` `source=[aws.ecs]`, `detail-type=[ECS Task State Change]`, `detail.lastStatus=[STOPPED]`, `detail.containers.exitCode=[{anything-but:[0]}]`, `detail.taskDefinitionArn=[{prefix: …task-definition/intellichoice-staging-ops-task}]`, `detail.clusterArn=[…cluster/intellichoice-staging]`. The documented restraint is real, not merely documented.
- **Evidence source**: `aws scheduler list-schedules` (all groups, no name filter) / `aws events list-rules --name-prefix intellichoice-staging` / `aws events describe-rule --name intellichoice-staging-ops-task-failed`
- **Observed at**: 2026-08-20T00:05:5xZ (LANE-C)
- **Limitations**: only the "does it run" half is answered. Re-measuring the underlying eligibility figures needs a query against the private Postgres → forbidden (§3); the item is **split**, not closed. The ops-task log-line search for `checkpoint_retention` would need log content, which no lane may read.
- **Classification**: DEPLOYED_CONFIRMED (no schedule — as configured)

#### WORK-35 — does AWS hold the `session-consolidate` schedule, and has it fired unattended for ≥1 week?

- **Claim ID**: WORK-35
- **Previous repository-side classification**: CONFIGURED_NOT_RUNTIME_VERIFIED → LOCALLY_VERIFIED (code half) — DRIFT-102
- **Intended state**: the schedule is declared ENABLED **and** §2.6 criterion 6 needs ≥1 week of unattended firing; the claimed idempotency numbers (36,929 rows, 0 written on a second run, 40 s vs 4m00s) are live facts.
- **Repository-configured state**: `session-consolidate` first in `locals.jobs`, enabled, `cron(0 18 * * ? *)`, `retry_attempts = 2`; app code, migrations, model/repo, job constant and four test files all exist; `checkpoint_retention_cli` deliberately unscheduled.
- **Observed deployed state**: present, `State: ENABLED`, `ScheduleExpression: cron(0 18 * * ? *)`, `ScheduleExpressionTimezone: UTC`, `RetryPolicy: {MaximumRetryAttempts: 2, MaximumEventAgeInSeconds: 3600}`, `Target.EcsParameters` = `intellichoice-staging-ops-task` / FARGATE / count 1 / both private subnets / `AssignPublicIp: DISABLED`, container override `python -m learning_api.services.session_consolidation_cli` on container `ops-task`. **`CreationDate: 2026-08-16T04:10:34.918Z`**, never modified. **The arithmetic ceiling:** as of 2026-08-20T00:08Z the schedule has existed 3 days ~20 hours, so **at most four** firing opportunities have occurred (18:00Z on 08-16/17/18/19); **≥1 week of unattended firing is arithmetically impossible today**, earliest satisfaction **2026-08-23T18:00Z**. Independently, the instrument meant to measure it cannot: `JobCompletions` has zero datapoints ever and the heartbeat alarm has exactly one transition (INSUFFICIENT_DATA→ALARM, 2026-08-16T23:49:48Z) and has never been OK. Job **execution** is confirmed at the metadata level (ops-task log streams at 18:01/18:11/18:50 UTC on both 2026-08-18 and 2026-08-19); job **success** is not.
- **Evidence source**: `aws scheduler get-schedule --group-name default --name intellichoice-staging-session-consolidate` / `aws cloudwatch describe-alarm-history --alarm-name intellichoice-staging-job-session-consolidate-heartbeat --history-item-type StateUpdate --max-records 20` / `aws cloudwatch get-metric-statistics --namespace IntelliChoice/intellichoice-staging/pipeline --metric-name JobCompletions --dimensions Name=job,Value=session-consolidate --start-time <-14d> --end-time <now> --period 86400 --statistics Sum` / `aws logs describe-log-streams --log-group-name /ecs/intellichoice-staging-ops-task --order-by LastEventTime --descending`
- **Observed at**: 2026-08-20T00:05:5xZ (LANE-C, schedule); 00:04:35Z–00:06:02Z (LANE-B, alarm/metric)
- **Limitations**: `get-schedule` reports declared state, not execution. The claimed idempotency numbers cannot be verified read-only — they need log content or a database query. The heartbeat alarm's `Period` is 172800 s, so with ~4 days of schedule life its history is thin *and* structurally uninformative (RD-01). `CloudWatch Events USE1-ScheduledInvocation` actual **44** is a monthly account-wide counter with no per-schedule dimension — circumstantial support that scheduled invocations fire, not attribution.
- **Classification**: DEPLOYED_STATE_PARTIALLY_CONFIRMED — the adjudication rules the **schedule half DEPLOYED_CONFIRMED** (state, cron, timezone, target and retries all exact); the ≥1-week-firing half is not confirmable today, for two independent reasons (arithmetic, and RD-01's broken instrument). See `DEPLOYED_INFRA_DRIFT_REGISTER` RD-01

---

## 3. Deferred and out-of-scope items (14)

### 3.1 Deferred to Phase 3B-2 — behavioural (6)

- **REQ-46** — access-hint recall on current staging traffic. Needs a labelled query set run against the deployed RAG path; no control-plane call measures retrieval quality.
- **TEST-21** — do current test-suite counts match the quoted ones. Local `pytest` / `make test` execution, not AWS.
- **TEST-28** — re-run the suites and compare counts against the recorded ones. Same lane as TEST-21; execute the two together.
- **WORK-05** — do the quoted counts still hold on current HEAD. Local greps/counts.
- **WORK-13** — is the `journey-student.spec.ts` isolation defect behaviourally resolved. Needs `make e2e-staging` / a Playwright run. Standing hazard: Playwright shares the dev Postgres with pytest — never run it concurrently with `make test`.
- **WORK-29** — what a validation run produces and the measured reject threshold. Pipeline execution; any arm that invokes generation is a **paid** run needing explicit user approval and exported model ids, never an audit-phase default.

### 3.2 External to AWS (3)

- **ARCH-33** — has the deployed-version gate ever fired. GitHub Actions run history (`gh run list --workflow=deploy-staging.yml`). The deployed side of the same concern is already covered by WORK-06 and ARCH-34 and must not be double-counted.
- **SEC-23** — the LangSmith account's run-retention setting. A SaaS account setting with no in-repo expression at all, reachable only through LangSmith's console/API.
- **WORK-44** — is the 26-PR backlog actually cleared. GitHub state (`gh pr list`); cheap, but it belongs to the external lane.

### 3.3 Forbidden under read-only rules (5)

- **SEC-27** — do the `cost_reservations` rows exist in staging Postgres. Needs a `SELECT` against a `PubliclyAccessible: false` instance in a private subnet plus a resolved secret value.
- **TEST-04** — does a deployed container actually fail on a missing required env var. Demonstrating the fence means deregistering an env var and forcing a task start — a **mutation**. (Different blocker in kind from the other four.)
- **INT-29** — does the deployed knowledge store still hold the enrollment FAQ as `status: draft`. The knowledge store is a table in the private staging Postgres. A weaker proxy (ops-task ingestion log lines) would show that an ingest ran, not what it holds — and log content is unreadable in this phase anyway.
- **WORK-03** — has migration `8509c0486d8d` been applied to the deployed database. The table's existence is inside the private RDS instance; the available proxy is circumstantial.
- **WORK-20** — is migration `6538a95bc990` applied. `alembic_version` lives in the private staging Postgres.

Four of these five (SEC-27, INT-29, WORK-03, WORK-20) are **the same blocker wearing four hats**: the staging databases are `PubliclyAccessible: false` in private subnets and their credentials are Secrets Manager values. They are one structural limitation of read-only verification, not four independent gaps. All five are closed as **blocked-by-design**, not recorded as coverage failures.

---

## 4. Classification totals

Over the **42** inspected claims (one block each):

| Classification | Count | Claim IDs |
|---|---|---|
| DEPLOYED_CONFIRMED | **36** | ARCH-02, ARCH-03, ARCH-04, ARCH-07, ARCH-08, ARCH-10, ARCH-11, ARCH-12, ARCH-13, ARCH-14, ARCH-22, ARCH-28, ARCH-29, ARCH-30, ARCH-35, SEC-10, SEC-16, SEC-25, SEC-26, COST-15, COST-16, COST-17, COST-19, COST-21, COST-23, COST-24, COST-25, COST-26, COST-27, COST-28, COST-29, TEST-09, WORK-02, WORK-06, WORK-08, WORK-23 |
| DEPLOYED_DIFFERS_FROM_REPOSITORY | **1** | ARCH-15 |
| CONFIGURED_BUT_NOT_DEPLOYED | **0** | — |
| DEPLOYED_STATE_PARTIALLY_CONFIRMED | **3** | ARCH-34, REQ-50, WORK-35 |
| NOT_PRESENT_IN_DEPLOYED_STATE | **2** | COST-18, REQ-18 |
| UNVERIFIED | **0** | — (both 3A UNVERIFIED items resolved: ARCH-15 → DIFFERS, SEC-26 → CONFIRMED) |
| ACCESS_UNAVAILABLE | **0** | — (zero `AccessDenied` in all three lanes) |
| NOT_APPLICABLE | **0** | — |
| DEFERRED_BY_D152 | **0** | — (integration items were never queued to 3B-1) |
| **Total** | **42** | |

36 + 1 + 0 + 3 + 2 + 0 + 0 + 0 + 0 = **42**. Queue reconciliation: 42 inspected + 6 deferred to 3B-2 + 3 external + 5 forbidden = **56**.

Notes on two composite rows, so the arithmetic is readable rather than merely balanced:

- **REQ-50** counts once, under DEPLOYED_STATE_PARTIALLY_CONFIRMED. Its half (a) is DEPLOYED_CONFIRMED (SLO instrumentation is deployed); half (b) is the partial one (100-concurrent never demonstrated live).
- **WORK-35** counts once, under DEPLOYED_STATE_PARTIALLY_CONFIRMED. The adjudication rules its **schedule half** DEPLOYED_CONFIRMED; the ≥1-week-firing half is unconfirmable today.
- **COST-19** counts under DEPLOYED_CONFIRMED because its *configuration* is exact in AWS. Its runtime state is COST-18's finding and belongs to `DEPLOYED_INFRA_DRIFT_REGISTER` RD-01 — the config being exact is precisely why the broken instrument was not caught earlier.
