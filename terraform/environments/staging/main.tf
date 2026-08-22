data "aws_caller_identity" "current" {}

# D-244: what is *actually* running, read at plan time. `aws_ecs_task_definition` resolves
# the family to its latest ACTIVE revision - which is the revision `deploy-staging.yml`
# registered, not the one Terraform last wrote.
#
# Guarded by `adopt_deployed_image` because a data source cannot be `try()`d out of
# existence: on a brand-new environment there is no task definition to read and the lookup
# fails at plan time, before any fallback could apply. Set it false for the first apply,
# then leave it true forever.
data "aws_ecs_task_definition" "deployed" {
  for_each        = var.adopt_deployed_image ? toset(["learning-api", "chat-api"]) : toset([])
  task_definition = "${var.name_prefix}-${each.key}"
}

data "aws_ecs_container_definition" "deployed" {
  for_each        = data.aws_ecs_task_definition.deployed
  task_definition = each.value.id
  container_name  = each.key
}

locals {
  learning_api_ecr_url = module.ecr.repository_urls["learning-api"]
  chat_api_ecr_url     = module.ecr.repository_urls["chat-api"]

  # D-244 closes carry-over #8: **Terraform adopts the image the deploy last shipped,
  # rather than re-rendering the one pinned in `terraform.tfvars`.**
  #
  # Terraform owns `aws_ecs_task_definition` and `deploy-staging.yml` owns which image goes
  # in it. `lifecycle.ignore_changes` on the *service* stops Terraform fighting over which
  # revision is current, but the task-definition *resource* still renders `var.*_image_tag`
  # - so any Terraform change to the task definition silently reverted the deploy. That is
  # not hypothetical: D-242 applied a one-line env var and rolled both services back to a
  # months-old commit, and the tfvars pin is *still* `gha-70100623148d` while live runs
  # `gha-fedeabf67427`. The workaround on record was "re-run the deploy immediately after",
  # which is a procedure that has already been forgotten once.
  #
  # Reading the live container definition makes the two owners agree by construction: the
  # deploy stays the only thing that changes the image, and Terraform stops having an
  # opinion it was never the source of truth for. The tfvars pin survives only as the
  # bootstrap fallback for an environment that has no task definition yet - see
  # `adopt_deployed_image`.
  learning_api_image = try(
    data.aws_ecs_container_definition.deployed["learning-api"].image,
    "${local.learning_api_ecr_url}:${var.learning_api_image_tag}"
  )
  chat_api_image = try(
    data.aws_ecs_container_definition.deployed["chat-api"].image,
    "${local.chat_api_ecr_url}:${var.chat_api_image_tag}"
  )

  # S39: the OTel collector sidecar, from this account's *private* ECR mirror rather than
  # public.ecr.aws - the tasks have no NAT and cannot reach the public registry. Populate
  # the mirror with scripts/mirror-otel-collector.sh before changing the version here, or
  # the deploy fails at image pull and rolls back.
  otel_collector_image = "${module.ecr.repository_urls["aws-otel-collector"]}:${var.otel_collector_version}"

  # Bedrock model ARNs, computed from the same model IDs the apps are configured with so
  # IAM permissions always match what the app will actually request (S32/D-084). Two
  # shapes exist and need different handling:
  # - Plain foundation models (e.g. "anthropic.claude-sonnet-5") - account-less,
  #   region-scoped: arn:aws:bedrock:<region>::foundation-model/<id>.
  # - Cross-region inference profiles (e.g. "us.anthropic.claude-haiku-4-5-...", used
  #   because some models - Haiku 4.5 confirmed live during S32/D-084's Bedrock-quota
  #   troubleshooting - reject on-demand invocation with the bare model ID entirely and
  #   require a profile) - these ARE account-scoped
  #   (arn:aws:bedrock:<region>:<account>:inference-profile/<id>), *and* AWS also
  #   requires InvokeModel permission on the underlying foundation model across every
  #   region the profile might route to, hence the wildcard region below.
  bedrock_configured_model_ids = distinct([var.bedrock_tutor_model_id, var.bedrock_embedding_model_id])

  bedrock_model_arns = flatten([
    for model_id in local.bedrock_configured_model_ids : (
      can(regex("^(us|eu|apac|global)\\.", model_id))
      ? [
        "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${model_id}",
        "arn:aws:bedrock:*::foundation-model/${replace(model_id, "/^(us|eu|apac|global)\\./", "")}",
      ]
      : ["arn:aws:bedrock:${var.aws_region}::foundation-model/${model_id}"]
    )
  ])

  # Wildcard-scoped to this environment's own log-group naming convention, computed
  # without depending on the ecs-service modules' outputs - avoids a circular
  # dependency (iam's execution role needs to write to those log groups; ecs-service
  # needs iam's execution role ARN as an input).
  log_group_arns = [
    "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/${var.name_prefix}-*:*",
  ]

  # D-244: the same technique, one level narrower. The `awsemf` exporter runs under the
  # *task* role (the sidecar shares it with the app), and it must not be able to write into
  # the application log groups the five Bedrock metric filters read - so this names only
  # the `/emf` suffix rather than reusing `log_group_arns` above.
  metrics_log_group_arns = [
    "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/${var.name_prefix}-*/emf:*",
  ]
}

locals {
  # **D-406: everything that needs *general* internet egress from a private subnet.**
  #
  # The NAT gateway exists for exactly these, and the previous wiring
  # (`nat_gateway_enabled = var.langsmith_tracing_enabled`) was one consumer hardcoded as the
  # condition. That was true and became a trap: `youtube-sync` also runs in a private subnet with
  # `assign_public_ip = false`, and the YouTube Data API has no VPC endpoint - so switching tracing
  # off would have silently stripped that job's egress. `modules/vpc/main.tf` says of exactly this
  # class that "the failure surfaces only at runtime - `terraform plan` cannot see it, and here
  # neither could the collector's health".
  #
  # It was safe only because the sync was hardcoded `enabled = false` inside the module, i.e. safe
  # by an accident of where a flag lived. Named as a map rather than a bare `||` so the *reason*
  # NAT is on is readable in a plan diff, and so adding a third consumer is one line here rather
  # than a rediscovery of this comment.
  private_egress_consumers = {
    langsmith_tracing = var.langsmith_tracing_enabled
    youtube_sync      = var.youtube_sync_enabled
  }
  needs_private_egress = anytrue(values(local.private_egress_consumers))
}

module "vpc" {
  source      = "../../modules/vpc"
  name_prefix = var.name_prefix
  # Tied to the tracing flag rather than defaulted on: the endpoint bills per hour
  # whether or not a span ever crosses it, and it is useless when the sidecar is absent.
  xray_endpoint_enabled = var.enable_otel_tracing
  # D-214: private subnets get an internet route only because some third-party SaaS has no
  # PrivateLink equivalent, and the NAT bills per hour whether or not a byte crosses it - so it
  # follows its consumers rather than being defaulted on.
  #
  # **D-406: driven by `local.private_egress_consumers`, not by the tracing flag.** It used to read
  # `nat_gateway_enabled = var.langsmith_tracing_enabled`, which was correct while LangSmith was the
  # only such consumer and became a trap the moment a second one existed. See that local for the
  # failure it prevents.
  nat_gateway_enabled = local.needs_private_egress
  tags                = local.common_tags
}

# D-214: looked up rather than created by Terraform, matching how the YouTube API key is
# handled - the value is written once by a human with `aws secretsmanager create-secret` and
# never passes through the repo, a plan file, or state as anything but an ARN.
# D-214: the YouTube Data API key, created by hand the same way. Adopted into Terraform
# here because it was previously invisible to it - see the ops_task block below.
data "aws_secretsmanager_secret" "youtube_api_key" {
  name = "${var.name_prefix}/youtube-api-key"
}

data "aws_secretsmanager_secret" "langsmith_api_key" {
  count = var.langsmith_tracing_enabled ? 1 : 0
  name  = "${var.name_prefix}/langsmith-api-key"
}

locals {
  # LangSmith reads *unprefixed* env vars straight from the process environment - these are
  # deliberately not `LEARNING_`/`CHAT_` prefixed like the app's own settings, because the
  # langsmith client never goes through pydantic-settings. Verified against the installed
  # 0.10.5: `LANGSMITH_TRACING=true` flips `tracing_is_enabled()`, and `LANGSMITH_API_KEY`
  # is the key the client resolves.
  langsmith_env = var.langsmith_tracing_enabled ? {
    LANGSMITH_TRACING = "true"
    LANGSMITH_PROJECT = var.name_prefix
    # D-242: without this the client sends no `x-tenant-id` and LangSmith answers **403 on
    # every endpoint** - because this API key has no *default* workspace, so a request that
    # names no tenant is refused. That 403 cost two wrong diagnoses ("the multipart endpoint
    # is not entitled", then "the key is not a valid key"), because LangSmith returns the
    # same 403 for an unknown key as for a valid key with no tenant named. Sending *no* key
    # is what returns 401; 403 does not distinguish the two cases.
    #
    # Not a secret: a workspace id identifies a tenant, it does not authorize anything - the
    # API key does that. Same tier as the AWS account id already inlined throughout this file.
    LANGSMITH_WORKSPACE_ID = var.langsmith_workspace_id
  } : {}

  langsmith_secrets = var.langsmith_tracing_enabled ? {
    LANGSMITH_API_KEY = data.aws_secretsmanager_secret.langsmith_api_key[0].arn
  } : {}
}

module "alb" {
  source            = "../../modules/alb"
  name_prefix       = var.name_prefix
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  tags              = local.common_tags
}

# One shared SG for everything ECS launches (both services + the ops task) - a plain
# root resource, not created inside ecs-service, so RDS's "allow from the ECS task SG"
# rule and ecs-service's "needs the DB secret ARN" input don't form a circular module
# dependency (S32/D-084). Slightly coarser than per-service SGs (both ports open to both
# services) but all three are equally-trusted parts of the same deployment - not worth
# three near-identical SGs for a distinction with no real blast-radius difference.
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.name_prefix}-ecs-tasks-sg"
  description = "Shared ECS task SG (learning-api, chat-api, ops-task) - inbound from the ALB only"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "HTTP from the ALB (learning-api 8001, chat-api 8002)"
    from_port       = 8001
    to_port         = 8002
    protocol        = "tcp"
    security_groups = [module.alb.alb_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.name_prefix}-ecs-tasks-sg" })
}

resource "aws_ecs_cluster" "this" {
  name = var.name_prefix

  # Fills the S31 carry-over gap directly (CPU/memory/task-count metrics had no
  # deployed container runtime to scrape from until now).
  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.common_tags
}

module "ecr" {
  source = "../../modules/ecr"
  # S39: `aws-otel-collector` is a **mirror** of `public.ecr.aws/aws-observability/
  # aws-otel-collector`, not something this repo builds. It has to live in private ECR
  # because the ECS tasks run in private subnets with **no NAT gateway** (D-084's cost
  # posture) - they reach private ECR through the `ecr.dkr`/`ecr.api` interface endpoints
  # and S3 for layers, and `public.ecr.aws` is simply unroutable from there. Found live:
  # the first sidecar deploy failed with `CannotPullContainerError ... dial tcp
  # 75.2.101.78:443: i/o timeout` and retried until it was rolled back. A public-ECR
  # interface endpoint does not exist, so mirroring is the fix; a NAT gateway (~$32/mo for
  # one image pull) is not.
  #
  # Populate it with scripts/mirror-otel-collector.sh, which pins the digest and pushes
  # linux/arm64 to match `runtime_platform`.
  repository_names = ["learning-api", "chat-api", "aws-otel-collector"]
  tags             = local.common_tags
}

module "rds_postgres" {
  source                     = "../../modules/rds-postgres"
  name_prefix                = var.name_prefix
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  allowed_security_group_ids = [aws_security_group.ecs_tasks.id]
  tags                       = local.common_tags
}

module "rds_mysql" {
  source                     = "../../modules/rds-mysql"
  name_prefix                = var.name_prefix
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  allowed_security_group_ids = [aws_security_group.ecs_tasks.id]
  tags                       = local.common_tags
}

module "iam" {
  source      = "../../modules/iam"
  name_prefix = var.name_prefix
  secret_arns = concat(var.langsmith_tracing_enabled ? [data.aws_secretsmanager_secret.langsmith_api_key[0].arn] : [], [
    module.rds_postgres.master_user_secret_arn,
    module.rds_mysql.master_user_secret_arn,
    aws_secretsmanager_secret.jwt_signing_secret_learning.arn,
    aws_secretsmanager_secret.jwt_signing_secret_chat.arn,
    # S36/D-097: without these two the task execution role cannot read the new secrets and
    # both tasks fail to start with ResourceInitializationError - the secret injection
    # happens before the container runs, so it is a startup failure, not a runtime 500.
    aws_secretsmanager_secret.staging_token_shared_secret_learning.arn,
    aws_secretsmanager_secret.staging_token_shared_secret_chat.arn,
    # D-214: both of these were granted by hand and Terraform's plan wanted to *remove*
    # them - the youtube key silently (it is only read by the ops task, which nothing
    # alarms on), and langsmith not at all, since it did not exist yet. Secret injection
    # happens before the container runs, so losing the grant is a startup failure rather
    # than a runtime error, exactly as the S36 note above records.
    data.aws_secretsmanager_secret.youtube_api_key.arn,
  ])
  bedrock_model_arns = local.bedrock_model_arns
  log_group_arns     = local.log_group_arns
  # Empty when the sidecar is off: no collector, no EMF group, no reason to grant it.
  metrics_log_group_arns = var.enable_otel_tracing ? local.metrics_log_group_arns : []
  tags                   = local.common_tags

  # GitHub OIDC/deploy role: the repo now exists (S32/D-084's execution order deferred
  # this until it did) - see deploy-staging.yml.
  create_github_oidc_provider = true
  create_github_deploy_role   = true
  github_org                  = var.github_org
  github_repo                 = var.github_repo

  ecr_repository_arns  = values(module.ecr.repository_arns)
  ecs_cluster_arn      = aws_ecs_cluster.this.arn
  frontend_bucket_arns = [module.cloudfront_learning.bucket_arn, module.cloudfront_chat.bucket_arn]
  cloudfront_distribution_arns = [
    module.cloudfront_learning.distribution_arn,
    module.cloudfront_chat.distribution_arn,
  ]
}

# D-085: real, per-app, random JWT signing secrets - replaces the hardcoded, public
# `DEV_JWT_SECRET` module constant (D-006) that `JwtTokenVerifier` fell back to
# unconditionally before this session, with no override path at all. Two independent
# secrets, not one shared between the apps - see `chat_api.config.Settings.
# jwt_signing_secret`'s comment for why. Unexercised until a real go.intellichoice.org
# integration or a re-enabled `/dev/token` issues a token signed with the matching
# secret (same "provisioned, not yet exercised against real traffic" posture as
# D-025/D-035/D-046) - still real defense against someone forging a token offline using
# the public dev constant, which is the actual risk this closes.
resource "random_password" "jwt_signing_secret_learning" {
  length  = 64
  special = false
}

resource "random_password" "jwt_signing_secret_chat" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "jwt_signing_secret_learning" {
  name = "${var.name_prefix}/learning-api/jwt-signing-secret"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "jwt_signing_secret_learning" {
  secret_id     = aws_secretsmanager_secret.jwt_signing_secret_learning.id
  secret_string = random_password.jwt_signing_secret_learning.result
}

resource "aws_secretsmanager_secret" "jwt_signing_secret_chat" {
  name = "${var.name_prefix}/chat-api/jwt-signing-secret"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "jwt_signing_secret_chat" {
  secret_id     = aws_secretsmanager_secret.jwt_signing_secret_chat.id
  secret_string = random_password.jwt_signing_secret_chat.result
}

# S36/D-097: the shared secret that gates `/dev/token` on this staging environment - the
# audit sessions' (S36-S39) only authenticated path against live staging, since real auth
# does not exist until S44 and S35 correctly closed the unauthenticated one.
#
# Deliberately a Secrets Manager value rather than a `terraform.tfvars` string or an ECS
# env var: every prior gate on this endpoint was plain config, and S32/S33/S35 between them
# proved that a plain-config gate can be flipped by one edit, in one untracked working
# tree, without anything noticing for two days. Possession of a 64-char random secret is a
# different kind of gate. Same `random_password` + `secret_version` shape as the JWT
# secrets above, so this introduces no new pattern.
#
# STAGING ONLY. `terraform/environments/production` (S48) must never define these, and the
# app-side default is the empty string, which never matches (`staging_secret_matches`).
# Both resources and both env wirings are deleted at S44, when a real token issuer exists.
resource "random_password" "staging_token_shared_secret_learning" {
  length  = 64
  special = false
}

resource "random_password" "staging_token_shared_secret_chat" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "staging_token_shared_secret_learning" {
  name = "${var.name_prefix}/learning-api/staging-token-shared-secret"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "staging_token_shared_secret_learning" {
  secret_id     = aws_secretsmanager_secret.staging_token_shared_secret_learning.id
  secret_string = random_password.staging_token_shared_secret_learning.result
}

resource "aws_secretsmanager_secret" "staging_token_shared_secret_chat" {
  name = "${var.name_prefix}/chat-api/staging-token-shared-secret"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "staging_token_shared_secret_chat" {
  secret_id     = aws_secretsmanager_secret.staging_token_shared_secret_chat.id
  secret_string = random_password.staging_token_shared_secret_chat.result
}

module "ecs_service_learning_api" {
  source             = "../../modules/ecs-service"
  name               = "learning-api"
  name_prefix        = var.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  cluster_id         = aws_ecs_cluster.this.id
  listener_arn       = module.alb.listener_arn
  security_group_ids = [aws_security_group.ecs_tasks.id]
  # /students/* is unique to learning-api (no path collision with chat-api) so it's safe
  # as a plain path-pattern rule here. /dev/token collides with chat-api's own route of
  # the same name - handled separately below via header-disambiguated listener rules,
  # not here (D-084).
  path_patterns          = ["/learning/*", "/students/*"]
  listener_rule_priority = 100
  container_port         = 8001
  image                  = local.learning_api_image
  execution_role_arn     = module.iam.task_execution_role_arn
  task_role_arn          = module.iam.task_role_arn
  region                 = var.aws_region
  tags                   = local.common_tags
  # S34: `/readyz` actually pings Postgres+MySQL, unlike `/healthz` - see
  # `intellichoice_shared.db_ready`'s docstring for the real finding this fixes (the ALB
  # kept routing to a task that couldn't reach its database during S34's own local
  # DB-outage drill, since `/healthz` never reflected it).
  health_check_path = "/readyz"

  # AUD-F-29: 5 consecutive failures (~75s) instead of the default 3 (~45s), because this
  # service's readiness check fails under its *own* CPU saturation. See the module
  # variable's description for the measurement.
  health_check_unhealthy_threshold = 5

  # AUD-F-28 (D-122): this service is CPU-bound - a measured sweep on the old
  # 256/512 task showed throughput pinned at ~5.8 req/s from 10 concurrent sessions
  # upward, with latency growing exactly linearly in concurrency (Little's law holds to
  # within 4% at 10/25/50/100 VUs). So capacity here buys latency directly, and the
  # units are worth stating: at 256 CPU units the p95 <= 3s promise held only to ~8
  # concurrent sessions. 512 units x 2 tasks is 4x that. Note the ceiling above this:
  # the container runs ONE uvicorn worker (no --workers), so a single task cannot use
  # more than 1024 CPU units no matter what is provisioned - past that the lever is
  # task count, not task size.
  cpu    = 512
  memory = 1024

  # AUD-F-28: makes the 512 above mean something specific - 384 units to the app, 128 to
  # the otel sidecar - rather than depending on how an unset share is weighed. learning-api
  # only; see the module variable for why chat-api is deliberately left alone.
  pin_app_container_cpu = true

  # Criterion 7 asks for ">= 2 tasks with autoscaling active", which the D-121 run failed
  # on its own terms (desiredCount never left 1). Two tasks is also what makes AUD-F-29's
  # replacement survivable: losing one task no longer means losing all capacity.
  # `desired_count` is in `ignore_changes` on the service (autoscaling owns it once the
  # service exists), so it is `autoscaling_min_capacity` that actually moves a live service
  # off 1 - the desired_count below only matters to a from-scratch apply.
  desired_count            = 2
  autoscaling_min_capacity = 2

  # AUD-F-28: learning-api joins chat-api on ALB p95 step scaling. D-113 deliberately left
  # it on CPU target tracking ("no measurement says to move it") - this is that
  # measurement, and note it says something different from AUD-F-14's. CPU tracking here
  # is not *blind* (CPU pinned at 100%, the signal was perfect); it is too slow, needing 3
  # breaching minutes plus publish lag plus cooldown against a cohort-start burst that is
  # over in 3.5. The latency policy reacts after 2 breaching minutes and steps by 2 past
  # 10s. Neither policy can beat a burst that short - provisioned capacity does that - but
  # the faster of the two is the right one to keep.
  enable_latency_step_scaling = true
  alb_arn_suffix              = module.alb.alb_arn_suffix

  # S39: gives `LEARNING_OTEL_ENABLED=true` below something to export to. See the module's
  # `enable_otel_sidecar` variable for why a sidecar rather than a collector service.
  enable_otel_sidecar  = var.enable_otel_tracing
  otel_collector_image = local.otel_collector_image

  environment = merge(local.langsmith_env, {
    LEARNING_ENVIRONMENT = var.app_environment
    # D-085: independent second gate on /dev/token, ANDed with LEARNING_ENVIRONMENT==
    # "dev" in code - explicitly false here so flipping app_environment back to "dev"
    # alone (as S32 did once, for real browser testing) doesn't reopen the endpoint by
    # itself. Flip both deliberately, together, only for a temporary manual test.
    LEARNING_DEV_TOKEN_ENDPOINT_ENABLED = "false"
    LEARNING_BEDROCK_PROVIDER           = var.bedrock_provider
    LEARNING_BEDROCK_AWS_REGION         = var.aws_region
    LEARNING_BEDROCK_TUTOR_MODEL_ID     = var.bedrock_tutor_model_id
    LEARNING_BEDROCK_EMBEDDING_MODEL_ID = var.bedrock_embedding_model_id
    # S39: was hardcoded "false" through S38 because no collector existed in staging, which
    # is exactly why S38 could not evidence the "traces" half of its PII-floor line (D-102)
    # and why §2.6 criterion 9 stayed open. Now paired with the sidecar above; the app's
    # default endpoint (`http://localhost:4318`) already points at it, since awsvpc network
    # mode shares localhost across containers in a task.
    LEARNING_OTEL_ENABLED                = var.enable_otel_tracing ? "true" : "false"
    LEARNING_OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4318"
    LEARNING_LOG_LEVEL                   = "INFO"
    # D-092 (S33): plain (non-secret) DSN components - paired with the two JSON-key-
    # extracted secret components below, assembled into a real DSN by
    # `Settings._build_dsns_from_managed_secret_components`.
    LEARNING_DB_HOST       = module.rds_postgres.endpoint_address
    LEARNING_DB_PORT       = tostring(module.rds_postgres.endpoint_port)
    LEARNING_DB_NAME       = module.rds_postgres.db_name
    LEARNING_MYSQL_DB_HOST = module.rds_mysql.endpoint_address
    LEARNING_MYSQL_DB_PORT = tostring(module.rds_mysql.endpoint_port)
    # D-130: the org's local-time convention, which decides the attendance week. Passed
    # explicitly rather than left to the app's default so switching it after the org
    # confirms is a tfvars edit plus an apply - not a code change - and so the currently
    # deployed convention is readable from the task definition. Unprefixed on purpose:
    # both services must agree about what week it is.
    ORG_TIMEZONE        = var.org_timezone
    ORG_TIME_CONVENTION = var.org_time_convention
    ORG_TIME_CONFIRMED  = var.org_time_confirmed ? "true" : "false"
  })

  secrets = merge(local.langsmith_secrets, {
    # D-092 (S33): RDS's own AWS-managed, auto-rotated master-password secrets (real
    # rotation, no custom Lambda) - JSON-shaped, so each field is extracted
    # individually via the `:json-key::` ARN suffix rather than injected as one ready
    # DSN (replaces the old manually-maintained combined-DSN secret entirely).
    LEARNING_DB_USERNAME        = "${module.rds_postgres.master_user_secret_arn}:username::"
    LEARNING_DB_PASSWORD        = "${module.rds_postgres.master_user_secret_arn}:password::"
    LEARNING_MYSQL_DB_USERNAME  = "${module.rds_mysql.master_user_secret_arn}:username::"
    LEARNING_MYSQL_DB_PASSWORD  = "${module.rds_mysql.master_user_secret_arn}:password::"
    LEARNING_JWT_SIGNING_SECRET = aws_secretsmanager_secret.jwt_signing_secret_learning.arn
    # S36/D-097: staging only - see the resource definition above.
    LEARNING_STAGING_TOKEN_SHARED_SECRET = aws_secretsmanager_secret.staging_token_shared_secret_learning.arn
  })
}

module "ecs_service_chat_api" {
  source             = "../../modules/ecs-service"
  name               = "chat-api"
  name_prefix        = var.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  cluster_id         = aws_ecs_cluster.this.id
  listener_arn       = module.alb.listener_arn
  security_group_ids = [aws_security_group.ecs_tasks.id]
  # /me is unique to chat-api - see the matching comment on ecs_service_learning_api
  # above for why /dev/token is handled separately instead of listed here.
  path_patterns          = ["/chat/*", "/me"]
  listener_rule_priority = 200
  container_port         = 8002
  image                  = local.chat_api_image
  execution_role_arn     = module.iam.task_execution_role_arn
  task_role_arn          = module.iam.task_role_arn
  region                 = var.aws_region
  tags                   = local.common_tags
  # S34: see the matching comment on ecs_service_learning_api above.
  health_check_path = "/readyz"

  # AUD-F-14: chat-api waits on Bedrock, so CPU target-tracking can never fire on its
  # saturation (p95 31s at 15% CPU, measured live) - scale on ALB p95 latency instead.
  # S43/AUD-F-28: learning-api is now on this policy too, but for the opposite reason -
  # its CPU signal was accurate and merely slow. See its own comment above; the two
  # services share a mechanism, not a diagnosis.
  enable_latency_step_scaling = true
  alb_arn_suffix              = module.alb.alb_arn_suffix

  # D-344 authored `autoscaling_max_capacity = 1` here as a stopgap while D-349's relay was
  # built, and **it was never applied** - `terraform apply` is not part of `deploy-staging.yml`
  # and nobody ran it, so live stayed at the module default of 3 the whole time. Reverted
  # rather than left in place: a file claiming a capacity AWS does not have is worse than the
  # default it was trying to override, and the relay it was waiting for landed in the same
  # session anyway. The honest account is in D-344 itself.

  # S39: see the matching comment on ecs_service_learning_api above.
  enable_otel_sidecar  = var.enable_otel_tracing
  otel_collector_image = local.otel_collector_image

  environment = merge(local.langsmith_env, {
    CHAT_ENVIRONMENT = var.app_environment
    # D-085: mirrors LEARNING_DEV_TOKEN_ENDPOINT_ENABLED above - see that comment.
    CHAT_DEV_TOKEN_ENDPOINT_ENABLED           = "false"
    CHAT_BEDROCK_PROVIDER                     = var.bedrock_provider
    CHAT_BEDROCK_AWS_REGION                   = var.aws_region
    CHAT_BEDROCK_SCOPE_AND_INTENT_MODEL_ID    = var.bedrock_tutor_model_id
    CHAT_BEDROCK_RERANK_MODEL_ID              = var.bedrock_tutor_model_id
    CHAT_BEDROCK_RAG_ANSWER_MODEL_ID          = var.bedrock_tutor_model_id
    CHAT_BEDROCK_CALENDAR_EXTRACTION_MODEL_ID = var.bedrock_tutor_model_id
    CHAT_BEDROCK_EMBEDDING_MODEL_ID           = var.bedrock_embedding_model_id
    # S39: see the matching LEARNING_OTEL_ENABLED comment above.
    CHAT_OTEL_ENABLED                = var.enable_otel_tracing ? "true" : "false"
    CHAT_OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4318"
    CHAT_LOG_LEVEL                   = "INFO"
    # D-092 (S33): mirrors ecs_service_learning_api's identical env block above.
    CHAT_DB_HOST       = module.rds_postgres.endpoint_address
    CHAT_DB_PORT       = tostring(module.rds_postgres.endpoint_port)
    CHAT_DB_NAME       = module.rds_postgres.db_name
    CHAT_MYSQL_DB_HOST = module.rds_mysql.endpoint_address
    CHAT_MYSQL_DB_PORT = tostring(module.rds_mysql.endpoint_port)
    # D-130: identical to ecs_service_learning_api's block above, and identical on purpose -
    # the two services disagreeing about the attendance week would be a real defect, so they
    # read the same three unprefixed variables from the same tfvars.
    ORG_TIMEZONE        = var.org_timezone
    ORG_TIME_CONVENTION = var.org_time_convention
    ORG_TIME_CONFIRMED  = var.org_time_confirmed ? "true" : "false"
  })

  secrets = merge(local.langsmith_secrets, {
    # D-092 (S33): mirrors ecs_service_learning_api's identical secrets block above.
    CHAT_DB_USERNAME        = "${module.rds_postgres.master_user_secret_arn}:username::"
    CHAT_DB_PASSWORD        = "${module.rds_postgres.master_user_secret_arn}:password::"
    CHAT_MYSQL_DB_USERNAME  = "${module.rds_mysql.master_user_secret_arn}:username::"
    CHAT_MYSQL_DB_PASSWORD  = "${module.rds_mysql.master_user_secret_arn}:password::"
    CHAT_JWT_SIGNING_SECRET = aws_secretsmanager_secret.jwt_signing_secret_chat.arn
    # S36/D-097: staging only - see the resource definition above.
    CHAT_STAGING_TOKEN_SHARED_SECRET = aws_secretsmanager_secret.staging_token_shared_secret_chat.arn
  })
}

# /dev/token is registered as a literal, identical path in BOTH apps (outside any
# router prefix, so it isn't naturally disambiguated by path the way /learning/* and
# /chat/* are) - a plain path-pattern listener rule can't tell which app a `/dev/token`
# call is actually for on the one shared ALB. Disambiguated instead via the
# X-IntelliChoice-App header each CloudFront distribution's ALB origin already sends
# (see cloudfront-spa-api's custom_header) - found live via a real "Not found" bug
# report during S32/D-084 (the path-only fix alone silently routed every /dev/token call
# to whichever app's rule had the lower priority number, not necessarily the caller's).
resource "aws_lb_listener_rule" "dev_token_learning" {
  listener_arn = module.alb.listener_arn
  priority     = 90

  action {
    type             = "forward"
    target_group_arn = module.ecs_service_learning_api.target_group_arn
  }

  condition {
    path_pattern {
      values = ["/dev/token"]
    }
  }

  condition {
    http_header {
      http_header_name = "X-IntelliChoice-App"
      values           = ["learning"]
    }
  }
}

resource "aws_lb_listener_rule" "dev_token_chat" {
  listener_arn = module.alb.listener_arn
  priority     = 190

  action {
    type             = "forward"
    target_group_arn = module.ecs_service_chat_api.target_group_arn
  }

  condition {
    path_pattern {
      values = ["/dev/token"]
    }
  }

  condition {
    http_header {
      http_header_name = "X-IntelliChoice-App"
      values           = ["chat"]
    }
  }
}

module "ops_task" {
  source             = "../../modules/ops-task"
  name_prefix        = var.name_prefix
  image              = local.learning_api_image
  execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn      = module.iam.task_role_arn
  region             = var.aws_region
  tags               = local.common_tags

  environment = merge(local.langsmith_env, {
    # D-214: adopted into Terraform. These five were added directly to the task definition
    # by hand when the YouTube sync was first run, so Terraform did not know they existed -
    # and its plan wanted to replace the task definition *without* them, which would have
    # silently broken the sync and its Sunday cron. Caught by diffing the live definition
    # against this block before applying, not by the plan, which showed only "must be
    # replaced".
    YOUTUBE_CHANNEL_ID         = var.youtube_channel_id
    YOUTUBE_YOUTUBE_PROVIDER   = "youtube"
    YOUTUBE_BEDROCK_PROVIDER   = "bedrock"
    YOUTUBE_BEDROCK_AWS_REGION = var.aws_region

    LEARNING_ENVIRONMENT = "staging"

    # S40: the scheduled memory-consolidation job reads MEMORY_*-prefixed settings, and
    # every one of them defaults to something wrong for this environment:
    # `bedrock_provider` defaults to "mock" (a scheduled run would write mock-generated
    # facts into the real database - AUD-C-16's failure, automated weekly), and
    # `bedrock_consolidation_model_id` defaults to Sonnet 5, which this account's task role
    # is not granted (local.bedrock_model_arns is computed from the two *configured* ids),
    # so it would be denied even with the provider set. Both must be explicit.
    MEMORY_BEDROCK_PROVIDER               = var.bedrock_provider
    MEMORY_BEDROCK_AWS_REGION             = var.aws_region
    MEMORY_BEDROCK_CONSOLIDATION_MODEL_ID = var.bedrock_tutor_model_id
    # D-092 (S33): plain (non-secret) DSN components - `packages/db/engine.py`'s
    # `create_engine()` fallback (every standalone CLI: curriculum loader, knowledge
    # ingest, etc.), `alembic/env.py`, and `seed_mysql.py` all now check for these
    # unprefixed component env vars before falling back to DATABASE_URL/
    # SEED_MYSQL_URL - see D-092's full writeup in DECISIONS.md.
    DB_HOST       = module.rds_postgres.endpoint_address
    DB_PORT       = tostring(module.rds_postgres.endpoint_port)
    DB_NAME       = module.rds_postgres.db_name
    MYSQL_DB_HOST = module.rds_mysql.endpoint_address
    MYSQL_DB_PORT = tostring(module.rds_mysql.endpoint_port)
  })

  secrets = merge(local.langsmith_secrets, {
    YOUTUBE_YOUTUBE_API_KEY = data.aws_secretsmanager_secret.youtube_api_key.arn

    DB_USERNAME       = "${module.rds_postgres.master_user_secret_arn}:username::"
    DB_PASSWORD       = "${module.rds_postgres.master_user_secret_arn}:password::"
    MYSQL_DB_USERNAME = "${module.rds_mysql.master_user_secret_arn}:username::"
    MYSQL_DB_PASSWORD = "${module.rds_mysql.master_user_secret_arn}:password::"
  })
}

module "cloudfront_learning" {
  source      = "../../modules/cloudfront-spa-api"
  name_prefix = var.name_prefix
  app_name    = "learning"
  # learning_api's routers all sit under /learning/*, but main.py also registers a
  # handful of routes directly on `app` (not through a router, so no shared prefix):
  # /dev/token and /students/{id}/attendance. Missing these here meant they silently
  # fell through to the frontend's own CloudFront default behavior (S3 origin) instead
  # of the ALB - producing a same-origin 404 with a non-JSON (S3 XML) body, which then
  # crashed the frontend's error handler (`res.json()` fails on non-JSON, and the
  # catch block's `res.text()` fallback throws "body stream already read" since the
  # stream was already consumed) - found live via a real user report, not in review.
  # /healthz and /metrics deliberately stay excluded (internal-only, never meant to be
  # publicly reachable through CloudFront).
  api_path_patterns = ["/learning/*", "/dev/token", "/students/*"]
  alb_dns_name      = module.alb.alb_dns_name
  tags              = local.common_tags
}

module "cloudfront_chat" {
  source      = "../../modules/cloudfront-spa-api"
  name_prefix = var.name_prefix
  app_name    = "chat"
  # Same gap as cloudfront_learning above, chat_api's own version: /dev/token and /me
  # are registered directly on `app`, not under the /chat/* router prefix.
  api_path_patterns = ["/chat/*", "/dev/token", "/me"]
  alb_dns_name      = module.alb.alb_dns_name
  tags              = local.common_tags
}

# SPEC §5.30.3, closing traceability finding T-01 (D-124/D-125). Management events only,
# multi-region, log-file validation on, 90-day expiry on the bucket. The first copy of
# management events is free; the storage is what needs bounding. GuardDuty, the other half
# of T-01, is deliberately NOT here - deferred with a written reason in D-125, on the same
# always-on-cost argument that deferred WAF in D-087.
module "cloudtrail" {
  source      = "../../modules/cloudtrail"
  name_prefix = var.name_prefix
  aws_region  = var.aws_region
  tags        = local.common_tags
}

module "observability" {
  source             = "../../modules/observability"
  name_prefix        = var.name_prefix
  account_id         = data.aws_caller_identity.current.account_id
  notification_email = var.notification_email
  alb_arn_suffix     = module.alb.alb_arn_suffix
  services = {
    learning-api = module.ecs_service_learning_api.target_group_arn_suffix
    chat-api     = module.ecs_service_chat_api.target_group_arn_suffix
  }
  # D-213: the log groups the model-call metric filters read. Same two services, but a
  # separate map because these are log groups rather than target groups - a worker with no
  # load balancer still emits `bedrock_call` lines worth counting, and folding the two
  # together would make that impossible to express.
  log_group_names = {
    learning-api = module.ecs_service_learning_api.log_group_name
    chat-api     = module.ecs_service_chat_api.log_group_name
  }
  # D-244: where `pipeline_cli` and `loader` write. Both run here as ops tasks, so their
  # records were already reaching CloudWatch - just as unstructured text nothing could read.
  ops_task_log_group = module.ops_task.log_group_name

  # D-377: the scheduled jobs whose `<name>_job_complete` record is counted and heartbeat-
  # alarmed. **These strings must match `scheduled-jobs`'s own `locals.jobs` keys** - the
  # alarm carries `job` as a dimension, so a mismatch produces one that can never clear.
  # `youtube-sync` is deliberately absent: it is `enabled = false`, and a heartbeat alarm on
  # a schedule that is switched off would fire forever and teach everyone to ignore it.
  # The variable name says "nightly" and three of the four are; `memory-consolidate` is
  # weekly. Renaming the *variable* would be a plan no-op, but it touches the module, this
  # file and the parity tests, so it is left alone and the wording carries the correction
  # instead. Renaming the *alarm resource* is a different thing entirely and is not done:
  # that changes the terraform addresses and destroys and recreates four live alarms.
  nightly_job_events = [
    "session-consolidate",
    "chat-purge",
    "retention-purge",
    "memory-consolidate",
  ]
  # RD-01 (2026-08-22): the non-daily cadences, whose heartbeat window is 2x their own
  # schedule rather than the two-day default. `memory-consolidate` is `cron(30 18 ? * SUN *)`
  # in the `scheduled_jobs` module above, so 14 days - one missed week is a blip and two is an
  # alarm, the same rule the daily jobs get. On the two-day default it would have gone OK on
  # Sunday evening and been back in ALARM by Tuesday, paging for the rest of every week; it
  # never got that far only because the filter defect kept it in ALARM continuously.
  job_heartbeat_period_seconds = {
    memory-consolidate = 1209600
  }
  # Staging traffic is synthetic - the e2e suite is most of it - so there is no honest floor
  # to put under "sessions completed in a day". Left at 0 (disabled) rather than guessed at;
  # this is the one alarm in D-377 that needs a real usage baseline before it means anything,
  # and inventing a threshold here is how an alarm becomes noise on day one.
  daily_completed_sessions_floor = 0
  # D-244: 160 RDS metrics were being collected in this account and no alarm read one of
  # them. `max_connections_alarm` differs per engine because the two instance classes do
  # not share a connection ceiling - Postgres holds every session, checkpoint and question
  # row and carries the real concurrency; MySQL is the read-only profile adapter (D-082)
  # and should never be near its limit, so its threshold is set low enough that reaching it
  # is itself the finding.
  # 70% of the 1024 MiB task limit set above, shared between the app and the otel sidecar.
  # Named here rather than left to the module default because the number is only meaningful
  # next to the limit it is a fraction of: the point is to fire while there is still time to
  # act, since the OOM kill itself only surfaces later as an unexplained 5xx burst.
  ecs_memory_alarm_mib = 716
  database_instances = {
    postgres = {
      identifier            = module.rds_postgres.instance_identifier
      allocated_storage_gb  = module.rds_postgres.allocated_storage_gb
      max_connections_alarm = 80
    }
    mysql = {
      identifier            = module.rds_mysql.instance_identifier
      allocated_storage_gb  = module.rds_mysql.allocated_storage_gb
      max_connections_alarm = 40
    }
  }
  # AUD-X-13 / criterion 7: a healthy grounded chat turn measures p95 ~16s (four sequential
  # model calls, D-115), so the shared 3s paging threshold alarmed on normal conversation.
  # 20s is the measured p95 plus 25% headroom, and is the same number recorded as criterion
  # 7's live-staging threshold. learning-api keeps the module default of 3s - unmeasured
  # against real load, but its requests are not model calls.
  latency_p95_alarm_thresholds = {
    chat-api = 20
  }
  # AUD-F-33: alarm when either service sits above its own floor for an hour. The floors
  # differ - learning-api is pinned to 2 for criterion 7, chat-api uses the module's default
  # of 1 - so this is per-service and not one number. Deliberately NOT added to
  # deploy-staging.yml's canary alarm list: a service holding extra capacity is a cost
  # problem, and rolling a deploy back over it would be a worse outcome than the condition.
  ecs_cluster_name = aws_ecs_cluster.this.name
  capacity_floors = {
    learning-api = {
      ecs_service_name = module.ecs_service_learning_api.service_name
      min_capacity     = 2
    }
    chat-api = {
      ecs_service_name = module.ecs_service_chat_api.service_name
      min_capacity     = 1
    }
  }
  tags = local.common_tags
}

# S40 (AUD-F-06): the three schedulable maintenance jobs, running unattended. Sequenced
# early in Phase 0B because §2.6 criterion 6 requires >= 1 week of unattended runs, which
# makes this the only gate item bounded by the calendar rather than by effort - the earliest
# possible gate pass is one week after these land.
module "scheduled_jobs" {
  source      = "../../modules/scheduled-jobs"
  name_prefix = var.name_prefix
  # D-406: one switch, and NAT follows it via `local.private_egress_consumers`.
  youtube_sync_enabled = var.youtube_sync_enabled
  account_id           = data.aws_caller_identity.current.account_id

  ecs_cluster_arn = aws_ecs_cluster.this.arn
  # Family-level ARN (no ":<revision>"): every run resolves to the latest revision the
  # deploy workflow registered. See the variable's own docstring for why.
  ops_task_definition_arn_prefix = "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/${var.name_prefix}-ops-task"
  ops_container_name             = "ops-task"
  ops_task_log_group             = module.ops_task.log_group_name

  pass_role_arns = [
    module.iam.task_execution_role_arn,
    module.iam.task_role_arn,
  ]

  subnet_ids        = module.vpc.private_subnet_ids
  security_group_id = aws_security_group.ecs_tasks.id
  alerts_topic_arn  = module.observability.sns_topic_arn

  tags = local.common_tags
}
