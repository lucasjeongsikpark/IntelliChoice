# Restart-on-rotation for the two long-running API services (D-455, UD-14 answered 2026-09-29:
# option (b), automate it).
#
# **What D-455 found.** Both RDS master passwords are AWS-managed secrets with automatic
# rotation on a ~7-day cadence (D-092). The API tasks receive them as ECS container `secrets`
# (`valueFrom` the managed secret), which ECS resolves **once, at task start**. After a rotation
# the pooled connections that already exist keep working - neither Postgres nor MySQL
# re-authenticates an established session - so health checks and single users stay green,
# while every *new* connection the pool opens under load fails with `InvalidPasswordError`.
# Staging ran that way for a day before the 2026-08-29 stress test found it; it had been masked
# for a month only because a deploy (which replaces the tasks) had always followed within days.
#
# **Why the tasks cannot notice it themselves.** The password is an environment variable baked
# into the container at start; the app never talks to Secrets Manager and has no signal that
# the value went stale. Replacing the tasks is the only thing that re-reads it - which is what
# the manual first response in INCIDENT_RESPONSE.md (`update-service --force-new-deployment`)
# does, and exactly what this module automates. No change to the rotation cadence, the secrets,
# the task definitions or the deploy workflow; the trigger is the rotation event only, not
# a schedule.
#
# **Why both services restart on either secret.** Each app holds credentials for *both*
# databases (Postgres for its own tables, MySQL for the read-only profile adapter, D-082), so a
# rotation of either secret leaves both apps with one stale password. The two secrets rotate
# independently (observed hours apart), so this fires - and restarts both services - once per
# secret per cycle. Each restart is an ordinary rolling deployment (100% minimum healthy,
# circuit breaker with rollback, in `modules/ecs-service`), so the cost is a few minutes of
# double task count, not downtime.
#
# **Why the ops task is out of scope.** The nightly jobs are one-off `run-task` launches that
# resolve the secret afresh each run, which is why their heartbeats stayed green through D-455.
# There is no long-lived ops task to restart.
#
# **A deploy in flight is not a conflict.** ECS serializes deployments on a service: a
# forced new deployment during a workflow-driven one simply becomes the newest deployment and
# supersedes it, using the service's *current* task definition - which is whatever the deploy
# workflow last set, since Terraform `ignore_changes` it. No guard, lock or retry is needed.
#
# **Why an alarm, not just the log line (D-377).** A rotation that did not restart the tasks is
# the D-455 outage itself, silently re-armed for a week, so the Lambda's failure pages on the
# D-401 paging topic. The handler raises on any failed `UpdateService`, which is what makes a
# failure countable in `Errors` at all.

terraform {
  required_providers {
    # The inline handler is zipped at plan time. Declared here, not in the environment's
    # `versions.tf`, because this module is the only consumer (spec Revision 1).
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

locals {
  function_name = "${var.name_prefix}-rotation-restart"

  # UpdateService is authorised on the *service* ARN, which lives under its cluster.
  service_arns = [
    for s in var.service_names :
    "arn:aws:ecs:${var.region}:${var.account_id}:service/${var.ecs_cluster_name}/${s}"
  ]
}

# Secrets Manager emits `RotationSucceeded` as a service event, delivered to EventBridge through
# the account's CloudTrail trail (`modules/cloudtrail`). Read from this account's CloudTrail
# history on 2026-09-29: `eventType = AwsServiceEvent`, `invokedBy = secretsmanager.amazonaws.com`,
# the full secret ARN in `additionalEventData.SecretId` - for both RDS secrets, every week.
#
# `eventName` is matched exactly, so `RotationStarted` (a minute earlier in every cycle) and
# `RotationFailed`/`RotationAbandoned` never trigger a restart: restarting before the new
# password is live would re-read the *old* one. The SecretId list scopes it to the two RDS
# secrets; the JWT and staging-token secrets in this account do not rotate, and would not need
# a restart of this kind if they did.
resource "aws_cloudwatch_event_rule" "rotation_succeeded" {
  name        = "${var.name_prefix}-rds-secret-rotated"
  description = "RDS master secret rotation succeeded - force a new deployment of the API services (D-455)."

  event_pattern = jsonencode({
    source      = ["aws.secretsmanager"]
    detail-type = ["AWS Service Event via CloudTrail"]
    detail = {
      eventSource = ["secretsmanager.amazonaws.com"]
      eventName   = ["RotationSucceeded"]
      additionalEventData = {
        SecretId = var.secret_arns
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "rotation_succeeded_lambda" {
  rule      = aws_cloudwatch_event_rule.rotation_succeeded.name
  target_id = "rotation-restart"
  arn       = aws_lambda_function.this.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  # Only this rule may invoke the function.
  source_arn = aws_cloudwatch_event_rule.rotation_succeeded.arn
}

data "archive_file" "handler" {
  type = "zip"
  # The handler file alone - `test_handler.py` beside it stays out of the bundle.
  source_file = "${path.module}/lambda/handler.py"
  # Under the gitignored `.terraform/` of whichever root runs the plan, not the module tree.
  output_path = "${path.root}/.terraform/build/rotation-restart-handler.zip"
}

# Created by Terraform, before the function, so the retention is ours: a log group that Lambda
# creates implicitly on first invocation never expires.
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_lambda_function" "this" {
  function_name = local.function_name
  description   = "Force a new deployment of the API services after an RDS secret rotation (D-455)."
  role          = aws_iam_role.lambda.arn

  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.handler.output_path
  source_code_hash = data.archive_file.handler.output_base64sha256

  # Two UpdateService calls take well under a second each; 30 s is headroom, not a budget.
  timeout     = 30
  memory_size = 128

  # Asynchronous invocation keeps Lambda's default of two retries on a function error. A retry
  # re-issues the forced deployment for both services, which is harmless (the newest deployment
  # wins - see the header) and is the right response to a transient ECS API error. Each failed attempt
  # counts in `Errors`, so the alarm still fires even if a retry then succeeds.
  environment {
    variables = {
      ECS_CLUSTER_NAME  = var.ecs_cluster_name
      ECS_SERVICE_NAMES = join(",", var.service_names)
    }
  }

  tags = var.tags

  depends_on = [
    aws_cloudwatch_log_group.this,
    aws_iam_role_policy.lambda,
  ]
}

resource "aws_iam_role" "lambda" {
  name = local.function_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
      # Confused-deputy guard, as in `scheduled-jobs`: only this account's Lambda service.
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.account_id }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.function_name}-update-service"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # The two API services by ARN - nothing else in the cluster, and no other ECS action.
        Effect   = "Allow"
        Action   = ["ecs:UpdateService"]
        Resource = local.service_arns
      },
      {
        # The service's task definition names these roles, and a new deployment hands them to
        # the new tasks; without PassRole the forced deployment can be denied.
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = var.pass_role_arns
        Condition = {
          StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      },
      {
        # Its own log group's streams only. No CreateLogGroup: the group is Terraform's, above.
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.this.arn}:*"
      },
    ]
  })

  lifecycle {
    # The service ARNs above are assembled from the cluster *name*; this proves the name and the
    # cluster ARN the environment passes agree, so a typo cannot scope the policy to a cluster
    # the services are not in (which would fail only at the next rotation, i.e. silently).
    precondition {
      condition     = var.ecs_cluster_arn == "arn:aws:ecs:${var.region}:${var.account_id}:cluster/${var.ecs_cluster_name}"
      error_message = "ecs_cluster_arn does not match region/account_id/ecs_cluster_name."
    }
  }
}

# Pages, rather than going to the informational topic (D-401): a failed invocation means both
# services may still hold a rotated-out password - the D-455 outage, waiting for load.
resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${local.function_name}-errors"
  alarm_description   = "D-455: the restart-on-rotation Lambda failed - the API tasks may hold a rotated-out DB password. Run the manual force-new-deployment in INCIDENT_RESPONSE.md."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  # The function runs about twice a week; no invocations is the normal state, not a breach.
  treat_missing_data = "notBreaching"
  dimensions = {
    FunctionName = aws_lambda_function.this.function_name
  }
  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]
  tags          = var.tags
}
