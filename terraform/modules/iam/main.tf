data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Shared ECS task execution role (used by the ECS agent to pull images, write logs,
# and resolve `secrets` block references) - identical permissions needs across
# learning-api/chat-api/the migration-runner task, so one role for all three rather
# than three near-identical roles (D-084: match current reality, not a hypothetical
# future divergence).
resource "aws_iam_role" "task_execution" {
  name               = "${var.name_prefix}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "task_execution_extra" {
  statement {
    sid       = "ReadAppSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secret_arns
  }

  statement {
    sid       = "WriteAppLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = var.log_group_arns
  }
}

resource "aws_iam_role_policy" "task_execution_extra" {
  name   = "${var.name_prefix}-task-execution-extra"
  role   = aws_iam_role.task_execution.id
  policy = data.aws_iam_policy_document.task_execution_extra.json
}

# Shared ECS task role (assumed by the running application code itself, e.g. for
# Bedrock calls) - both apps invoke the same configured model IDs, so one role
# covers both (see task_execution's comment above for the same reasoning).
resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "task_bedrock" {
  # Covers both TitanEmbeddingProvider's plain invoke_model calls and
  # AnthropicBedrockProvider's converse calls (confirmed live - both use the same
  # bedrock:InvokeModel action/resource shape, just different boto3 methods on the same
  # bedrock-runtime client). A separate Bedrock Mantle grant (bedrock-mantle:
  # CreateInference on a project/default resource - a completely different IAM surface)
  # existed here through S32/D-084's model-access investigation but was removed once
  # every flagship model on that surface turned out to be blocked account-wide by an
  # AWS-Sales-only access gate, unrelated to IAM.
  statement {
    sid       = "InvokeConfiguredBedrockModels"
    actions   = ["bedrock:InvokeModel"]
    resources = var.bedrock_model_arns
  }

  # ECS Exec (`aws ecs execute-command`) - used for the one-off migration/seed/ops task
  # and ad-hoc debugging, since private-subnet tasks have no other reachable shell
  # (no bastion, no NAT). No resource-level scoping exists for these SSM actions.
  statement {
    sid = "EcsExecChannels"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }

  # S39: what the aws-otel-collector sidecar needs to ship spans to X-Ray. None of these
  # actions support resource-level scoping (X-Ray segments have no ARN to name), so `*` is
  # the only expressible form - the same situation as the SSM statement above. Granted to
  # the task role because the sidecar shares it with the app container.
  statement {
    sid = "OtelCollectorXRayExport"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
      "xray:GetSamplingStatisticSummaries",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "task_bedrock" {
  name   = "${var.name_prefix}-task-bedrock"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_bedrock.json
}

# --- GitHub Actions OIDC (deploy-time; deliberately deferred until a repo exists) ---
# No long-lived AWS access keys in GitHub - the deploy workflow assumes this role via
# GitHub's OIDC token instead. create_github_oidc_provider/create_github_deploy_role
# stay false until the repo is created (D-084's execution order): the trust policy
# below needs the real org/repo to scope correctly, and an AWS account should have at
# most one GitHub OIDC provider, so re-use an existing one via github_oidc_provider_arn
# if this account already has one.

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub's OIDC token-signing thumbprint (well-known, documented by GitHub/AWS -
  # https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect).
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = var.tags
}

locals {
  github_oidc_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : var.github_oidc_provider_arn

  # S34: derived from var.ecs_cluster_arn (`arn:aws:ecs:<region>:<account>:cluster/<name>`)
  # rather than adding three redundant input variables - same "split the ARN" pattern
  # `ecs-service`'s own `local.cluster_name` already uses.
  ecs_region       = split(":", var.ecs_cluster_arn)[3]
  ecs_account_id   = split(":", var.ecs_cluster_arn)[4]
  ecs_cluster_name = element(split("/", var.ecs_cluster_arn), 1)
}

data "aws_iam_policy_document" "github_deploy_assume" {
  count = var.create_github_deploy_role ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      # Any branch/ref/PR in this one repo - deploy_staging.yml itself only triggers
      # on push to main, so this is a coarser ceiling than the actual trigger, not the
      # enforcement point.
      #
      # S34: `@*` after both org and repo, not the plain `org/repo` shape GitHub's own
      # OIDC docs lead with - found live via a real `AssumeRoleWithWebIdentity` denial
      # on this workflow's first-ever run, root-caused via CloudTrail (which logs the
      # denied principal's actual `sub`, unlike the GitHub Actions log). This account's
      # real token's `sub` is `repo:lucasjeongsikpark@69391959/IntelliChoice@1310320932:
      # ref:refs/heads/main` - GitHub's newer OIDC tokens append each immutable numeric
      # owner/repo ID after `@` (survives an org/repo rename reusing the same name, a
      # anti-hijacking hardening GitHub added after the plain `org/repo:*` pattern this
      # docs' examples still show was written). The `@*` requires the literal "@"
      # marker in the real position, tighter than a bare trailing wildcard would be.
      values = ["repo:${var.github_org}@*/${var.github_repo}@*:*"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  count                = var.create_github_deploy_role ? 1 : 0
  name                 = "${var.name_prefix}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_deploy_assume[0].json
  permissions_boundary = var.deploy_role_permissions_boundary_arn != "" ? var.deploy_role_permissions_boundary_arn : null
  tags                 = var.tags
}

# Deliberately narrow: exactly what deploy-staging.yml does (build+push images,
# register a new task-def revision, force a new deployment, run the one-off ops-task,
# sync the built frontends, invalidate CloudFront) - never `terraform apply` (CI is
# meant to never run that unattended, see the ecs-service modules'
# `lifecycle.ignore_changes = [task_definition]` comment for why).
data "aws_iam_policy_document" "github_deploy_permissions" {
  count = var.create_github_deploy_role ? 1 : 0

  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # this action doesn't support resource-level scoping
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
    ]
    resources = var.ecr_repository_arns
  }

  statement {
    sid = "EcsDeploy"
    actions = [
      # RegisterTaskDefinition/Describe* don't support resource-level scoping (AWS IAM
      # limitation for these specific actions) - UpdateService/RunTask/DescribeTasks are
      # scoped to this cluster below.
      "ecs:RegisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeServices",
    ]
    resources = ["*"]
  }

  # S34: split out of a single over-broad "EcsClusterScoped" statement - found live via
  # a real `ecs:RunTask` `AccessDenied` on this workflow's first-ever run.
  # `ecs:RunTask`/`ecs:UpdateService` don't accept a *cluster* ARN as their resource at
  # all (RunTask's resource is the task-definition ARN being run; UpdateService's is the
  # service ARN, format `service/<cluster-name>/<service-name>`, a different ARN
  # "resource type" segment than `cluster/<cluster-name>` entirely) - the old
  # `[var.ecs_cluster_arn, "${var.ecs_cluster_arn}/*"]` pattern silently authorized
  # nothing for either action; nothing had ever actually exercised `ecs:RunTask`/
  # `ecs:UpdateService` against a real AWS account before this session (deploy-
  # staging.yml itself was written but never run). Cluster scoping for RunTask instead
  # uses the dedicated `ecs:cluster` condition key, AWS's documented mechanism for
  # exactly this.
  statement {
    sid       = "EcsRunTask"
    actions   = ["ecs:RunTask"]
    resources = ["arn:aws:ecs:${local.ecs_region}:${local.ecs_account_id}:task-definition/${var.name_prefix}-*"]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [var.ecs_cluster_arn]
    }
  }

  statement {
    sid       = "EcsUpdateService"
    actions   = ["ecs:UpdateService"]
    resources = ["arn:aws:ecs:${local.ecs_region}:${local.ecs_account_id}:service/${local.ecs_cluster_name}/*"]
  }

  # DescribeTasks' resource is the *task* ARN (assigned dynamically at RunTask time, not
  # knowable ahead of time by this policy) - `Resource: "*"` matches the same precedent
  # `EcsDeploy` above already uses for the other Describe*-style actions.
  statement {
    sid       = "EcsDescribeTasks"
    actions   = ["ecs:DescribeTasks"]
    resources = ["*"]
  }

  # References the task_execution/task roles created earlier in this same module
  # directly, not via a variable - they can't be passed in from outside since that
  # would make the module depend on its own output.
  statement {
    sid       = "PassEcsRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.task_execution.arn, aws_iam_role.task.arn]
  }

  statement {
    sid       = "SyncFrontendBuckets"
    actions   = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = flatten([for arn in var.frontend_bucket_arns : [arn, "${arn}/*"]])
  }

  statement {
    sid       = "InvalidateCloudFront"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = var.cloudfront_distribution_arns
  }

  # S34: deploy-staging.yml's post-deploy canary bake polls these alarms' state before
  # declaring a deploy successful - DescribeAlarms doesn't support resource-level scoping
  # (same AWS limitation as the Describe*/RegisterTaskDefinition actions above).
  statement {
    sid       = "CanaryAlarmCheck"
    actions   = ["cloudwatch:DescribeAlarms"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  count  = var.create_github_deploy_role ? 1 : 0
  name   = "${var.name_prefix}-github-deploy"
  role   = aws_iam_role.github_deploy[0].id
  policy = data.aws_iam_policy_document.github_deploy_permissions[0].json
}
