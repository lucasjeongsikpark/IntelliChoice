data "aws_caller_identity" "current" {}

locals {
  learning_api_ecr_url = module.ecr.repository_urls["learning-api"]
  chat_api_ecr_url     = module.ecr.repository_urls["chat-api"]

  learning_api_image = "${local.learning_api_ecr_url}:${var.learning_api_image_tag}"
  chat_api_image     = "${local.chat_api_ecr_url}:${var.chat_api_image_tag}"

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
}

module "vpc" {
  source      = "../../modules/vpc"
  name_prefix = var.name_prefix
  tags        = local.common_tags
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
  source           = "../../modules/ecr"
  repository_names = ["learning-api", "chat-api"]
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
  secret_arns = [
    module.rds_postgres.master_user_secret_arn,
    module.rds_mysql.master_user_secret_arn,
    aws_secretsmanager_secret.jwt_signing_secret_learning.arn,
    aws_secretsmanager_secret.jwt_signing_secret_chat.arn,
  ]
  bedrock_model_arns = local.bedrock_model_arns
  log_group_arns     = local.log_group_arns
  tags               = local.common_tags

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

  environment = {
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
    LEARNING_OTEL_ENABLED               = "false" # no hosted collector deployed this session (D-084) - CloudWatch Logs + Container Insights cover the immediate gap
    LEARNING_LOG_LEVEL                  = "INFO"
    # D-092 (S33): plain (non-secret) DSN components - paired with the two JSON-key-
    # extracted secret components below, assembled into a real DSN by
    # `Settings._build_dsns_from_managed_secret_components`.
    LEARNING_DB_HOST       = module.rds_postgres.endpoint_address
    LEARNING_DB_PORT       = tostring(module.rds_postgres.endpoint_port)
    LEARNING_DB_NAME       = module.rds_postgres.db_name
    LEARNING_MYSQL_DB_HOST = module.rds_mysql.endpoint_address
    LEARNING_MYSQL_DB_PORT = tostring(module.rds_mysql.endpoint_port)
  }

  secrets = {
    # D-092 (S33): RDS's own AWS-managed, auto-rotated master-password secrets (real
    # rotation, no custom Lambda) - JSON-shaped, so each field is extracted
    # individually via the `:json-key::` ARN suffix rather than injected as one ready
    # DSN (replaces the old manually-maintained combined-DSN secret entirely).
    LEARNING_DB_USERNAME        = "${module.rds_postgres.master_user_secret_arn}:username::"
    LEARNING_DB_PASSWORD        = "${module.rds_postgres.master_user_secret_arn}:password::"
    LEARNING_MYSQL_DB_USERNAME  = "${module.rds_mysql.master_user_secret_arn}:username::"
    LEARNING_MYSQL_DB_PASSWORD  = "${module.rds_mysql.master_user_secret_arn}:password::"
    LEARNING_JWT_SIGNING_SECRET = aws_secretsmanager_secret.jwt_signing_secret_learning.arn
  }
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

  environment = {
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
    CHAT_OTEL_ENABLED                         = "false"
    CHAT_LOG_LEVEL                            = "INFO"
    # D-092 (S33): mirrors ecs_service_learning_api's identical env block above.
    CHAT_DB_HOST       = module.rds_postgres.endpoint_address
    CHAT_DB_PORT       = tostring(module.rds_postgres.endpoint_port)
    CHAT_DB_NAME       = module.rds_postgres.db_name
    CHAT_MYSQL_DB_HOST = module.rds_mysql.endpoint_address
    CHAT_MYSQL_DB_PORT = tostring(module.rds_mysql.endpoint_port)
  }

  secrets = {
    # D-092 (S33): mirrors ecs_service_learning_api's identical secrets block above.
    CHAT_DB_USERNAME        = "${module.rds_postgres.master_user_secret_arn}:username::"
    CHAT_DB_PASSWORD        = "${module.rds_postgres.master_user_secret_arn}:password::"
    CHAT_MYSQL_DB_USERNAME  = "${module.rds_mysql.master_user_secret_arn}:username::"
    CHAT_MYSQL_DB_PASSWORD  = "${module.rds_mysql.master_user_secret_arn}:password::"
    CHAT_JWT_SIGNING_SECRET = aws_secretsmanager_secret.jwt_signing_secret_chat.arn
  }
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

  environment = {
    LEARNING_ENVIRONMENT = "staging"
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
  }

  secrets = {
    DB_USERNAME       = "${module.rds_postgres.master_user_secret_arn}:username::"
    DB_PASSWORD       = "${module.rds_postgres.master_user_secret_arn}:password::"
    MYSQL_DB_USERNAME = "${module.rds_mysql.master_user_secret_arn}:username::"
    MYSQL_DB_PASSWORD = "${module.rds_mysql.master_user_secret_arn}:password::"
  }
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

module "observability" {
  source             = "../../modules/observability"
  name_prefix        = var.name_prefix
  notification_email = var.notification_email
  alb_arn_suffix     = module.alb.alb_arn_suffix
  services = {
    learning-api = module.ecs_service_learning_api.target_group_arn_suffix
    chat-api     = module.ecs_service_chat_api.target_group_arn_suffix
  }
  tags = local.common_tags
}
