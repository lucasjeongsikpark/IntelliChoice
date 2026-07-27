# Unattended schedules for the recurring maintenance jobs (§2.5, §2.6 criterion 6).
#
# Before this existed, `aws events list-rules` and `aws scheduler list-schedules` were both
# empty and all four jobs were `make` targets a human ran (AUD-F-06) - which meant the
# 90-day `chat-purge` retention promise depended on someone remembering. Criterion 6 wants
# them running unattended for >= 1 week, so this is on the critical path to the gate.
#
# EventBridge **Scheduler** (`aws_scheduler_schedule`), not an EventBridge **Rule** with a
# cron: Scheduler is the purpose-built service for this, gives an explicit timezone (no DST
# guessing), a per-target retry policy, and a flexible-time-window control - all of which a
# rule target would need hand-rolling.
#
# Three jobs are defined, **two are enabled**, and one of the four is absent entirely:
#
# - `chat-purge`, `memory-consolidate` - enabled.
# - `youtube-sync` - defined but DISABLED; see its own comment below. AUD-F-06 said three
#   jobs were schedulable, which was true of *running* them and false of running them
#   unattended.
# - `webcontent-sync` - not here at all: it rewrites tracked files under
#   `knowledge-content/` and prints "review the git diff before running org-load /
#   knowledge-load", so it is a content-authoring step that expects a human, and it would
#   fail against D-088's `readonlyRootFilesystem = true` regardless.

locals {
  # Times are UTC and staggered. The org is UTC+9, so 18:xx UTC is ~03:xx local - low
  # traffic, and far from the deploy window. Staggering keeps two jobs off the same RDS
  # instance at once and makes the logs trivially separable.
  #
  # `enabled` is per job, not just per module. AUD-F-06 counted three *schedulable* jobs
  # from a local run; testing them against the deployed environment showed that a job can
  # be schedulable and still be wrong to schedule, because the ops task supplies neither
  # `MEMORY_*` nor `YOUTUBE_*` provider settings and both default to
  # `bedrock_provider = "mock"`. A mocked job does not fail - it succeeds and writes
  # fabricated data into the real database, which is strictly worse. AUD-C-16 is what that
  # looks like after the fact: staging's entire RAG corpus is mock hash vectors because
  # ingestion ran with the mock, and nothing noticed for weeks.
  jobs = {
    chat-purge = {
      # Daily, not weekly. The cutoff is computed per run (`now - 90 days`), so a weekly
      # schedule would let a message sit up to 97 days against a 90-day promise.
      schedule    = "cron(10 18 * * ? *)"
      command     = ["python", "-m", "learning_api.services.tutor_chat_purge_cli"]
      description = "Delete tutor_chat_messages older than 90 days (SPEC retention promise)."
      # Idempotent and free: a retry can only re-delete rows already gone. A skipped day is
      # harmless too, since the next run uses a fresh cutoff.
      retry_attempts = 2
      # Purely deterministic SQL - no model, no provider setting to get wrong.
      enabled = true
    }
    memory-consolidate = {
      # Weekly. The CLI's window is a rolling [now - window_days, now) with window_days = 7.
      schedule    = "cron(30 18 ? * SUN *)"
      command     = ["python", "-m", "intellichoice_memory.consolidate_cli"]
      description = "Weekly semantic-memory consolidation (SPEC 5.15.4)."
      # **Zero retries, deliberately, and this is a cost decision rather than a reliability
      # one.** This is the only enabled job that calls a paid API, and its bound is
      # per-*run* (`bedrock_run_budget_cents`, default 200) - so three attempts is three
      # budgets, up to 600 cents, not one. It is idempotent per (student, week), so a retry
      # would be *correct* and still cost more than the failure it is papering over. A
      # missed week surfaces on the failure alarm below and can be run by hand.
      retry_attempts = 0
      # Safe only because the ops task now sets MEMORY_BEDROCK_* explicitly, including
      # pointing the model id at the one the IAM policy actually grants - the field's own
      # default is Sonnet 5, which this account's task role cannot invoke, so the wiring
      # is what makes this real rather than mocked *or* denied.
      enabled = true
    }
    youtube-sync = {
      schedule       = "cron(0 19 ? * SUN *)"
      command        = ["python", "-m", "intellichoice_youtube.sync_cli"]
      description    = "Weekly Khan Academy video catalog refresh (disabled - no real API key)."
      retry_attempts = 2
      # **Deliberately DISABLED, and this re-scopes AUD-F-06 from three jobs to two.**
      # `youtube_provider` defaults to "fake" and no real key exists (D-002's posture, still
      # true), so an unattended run would refresh the catalog from a *fake* source every
      # week - fabricated rows arriving on a schedule, indistinguishable in the database
      # from real ones. Failing loudly would be preferable; succeeding with invented data
      # is the worst outcome. Enable when a real `YOUTUBE_API_KEY` exists, together with
      # `YOUTUBE_BEDROCK_PROVIDER`/model wiring on the ops task.
      enabled = false
    }
  }
}

# The role Scheduler assumes to call RunTask on our behalf.
resource "aws_iam_role" "scheduler" {
  name = "${var.name_prefix}-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
      # Without this, any other AWS account could induce our Scheduler role to be assumed
      # on their behalf (the confused-deputy shape). Scoped to this account's schedules.
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.account_id }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "scheduler" {
  name = "${var.name_prefix}-scheduler-runtask"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ecs:RunTask"]
        # Every revision of this one family: `task_definition_arn` below is revision-pinned
        # by Terraform, but the deploy workflow registers new revisions, and a policy pinned
        # to one revision would silently start denying after the next deploy.
        Resource = ["${var.ops_task_definition_arn_prefix}:*"]
        Condition = {
          ArnEquals = { "ecs:cluster" = var.ecs_cluster_arn }
        }
      },
      {
        # RunTask hands these roles to the task; without PassRole the call is denied.
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = var.pass_role_arns
        Condition = {
          StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      },
    ]
  })
}

resource "aws_scheduler_schedule" "job" {
  for_each = local.jobs

  name        = "${var.name_prefix}-${each.key}"
  description = each.value.description
  group_name  = "default"

  # OFF, not a window: these are cheap jobs with no thundering-herd concern, and a
  # deterministic time makes "did last night's run happen?" answerable from the logs.
  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = each.value.schedule
  schedule_expression_timezone = "UTC"
  # Both gates must be on: the module-level kill switch and the per-job decision above.
  state = var.enabled && each.value.enabled ? "ENABLED" : "DISABLED"

  target {
    arn      = var.ecs_cluster_arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      # Family without a revision suffix, so each run picks up the latest revision the
      # deploy workflow registered - the same resolution `deploy-staging.yml` relies on for
      # its migration step.
      task_definition_arn = var.ops_task_definition_arn_prefix
      launch_type         = "FARGATE"
      task_count          = 1
      platform_version    = "LATEST"

      network_configuration {
        subnets          = var.subnet_ids
        security_groups  = [var.security_group_id]
        assign_public_ip = false
      }
    }

    # Scheduler merges this into the RunTask request, which is how the one shared ops-task
    # definition runs three different jobs.
    input = jsonencode({
      containerOverrides = [{
        name    = var.ops_container_name
        command = each.value.command
      }]
    })

    retry_policy {
      maximum_retry_attempts       = each.value.retry_attempts
      maximum_event_age_in_seconds = 3600
    }
  }
}

# Without this, a scheduled job that starts failing is invisible - which is AUD-F-12's
# lesson applied before it can happen again: the OTel collector accepted and discarded
# every span for an hour while every health signal stayed green, because nothing watched
# the one thing that mattered. A schedule that runs nightly and exits 1 every time looks
# identical, in every console, to one that is working.
resource "aws_cloudwatch_event_rule" "ops_task_failed" {
  name        = "${var.name_prefix}-ops-task-failed"
  description = "Any ops-task container that stops with a non-zero exit code."

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
    detail = {
      clusterArn = [var.ecs_cluster_arn]
      lastStatus = ["STOPPED"]
      containers = {
        # `anything-but` 0 also catches a null exitCode, which is what a task that failed
        # to *start* reports (the AUD-F-10 shape) rather than one that ran and failed.
        exitCode = [{ "anything-but" = [0] }]
      }
      # Scope to the ops-task family so the two long-running services' ordinary
      # deploy-time task churn does not page anyone.
      taskDefinitionArn = [{ prefix = var.ops_task_definition_arn_prefix }]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "ops_task_failed_sns" {
  rule      = aws_cloudwatch_event_rule.ops_task_failed.name
  target_id = "sns"
  arn       = var.alerts_topic_arn

  # The raw ECS event is a wall of JSON in an email. Pull out the few fields that answer
  # "which job, and how did it die?".
  input_transformer {
    input_paths = {
      task       = "$.detail.taskArn"
      definition = "$.detail.taskDefinitionArn"
      stopped    = "$.detail.stoppedReason"
      stoppedAt  = "$.detail.stoppedAt"
    }
    input_template = <<-EOT
      "A scheduled ops-task run failed on ${var.name_prefix}."
      "task definition: <definition>"
      "task: <task>"
      "stopped at: <stoppedAt>"
      "reason: <stopped>"
      "Logs: CloudWatch group ${var.ops_task_log_group}"
    EOT
  }
}
