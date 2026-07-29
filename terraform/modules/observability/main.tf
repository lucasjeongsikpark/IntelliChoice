resource "aws_budgets_budget" "monthly" {
  name         = "${var.name_prefix}-monthly-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.notification_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.notification_email]
  }
}

# S34: general alerting + the canary-bake rollback gate deploy-staging.yml polls after
# every deploy (see that workflow's own comments). One shared topic, not per-alarm -
# matches the budget alarm's own single-recipient posture (D-084); a real on-call
# rotation/PagerDuty integration is future work (same "no real notification channel yet"
# posture S31's carry-over already flagged for Prometheus alert rules).
resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
  tags = var.tags
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# S40: without this, an EventBridge **rule** cannot publish here, and it fails *silently*
# from the publisher's point of view - measured, not assumed: the scheduled-job failure rule
# fired with `Invocations = 1` and `FailedInvocations = 1` while SNS delivered **0**. The
# notification built to stop a scheduled job from failing unnoticed would itself have failed
# unnoticed, which is AUD-F-12's shape reproduced inside its own remedy.
#
# CloudWatch **alarms** already published fine on the default policy alone (4 delivered
# during S39's induction), which is exactly why this was worth testing rather than reasoning
# about: the two AWS services are not equivalent here, and the working one gave false
# confidence about the other.
#
# This resource *replaces* the implicit default policy, so the first statement reproduces it
# verbatim - dropping it would revoke the account's own Subscribe/SetTopicAttributes rights
# and orphan the email subscription.
resource "aws_sns_topic_policy" "alerts" {
  arn = aws_sns_topic.alerts.arn

  policy = jsonencode({
    Version = "2008-10-17"
    Id      = "${var.name_prefix}-alerts-policy"
    Statement = [
      {
        Sid       = "__default_statement_ID"
        Effect    = "Allow"
        Principal = { AWS = "*" }
        Action = [
          "SNS:GetTopicAttributes",
          "SNS:SetTopicAttributes",
          "SNS:AddPermission",
          "SNS:RemovePermission",
          "SNS:DeleteTopic",
          "SNS:Subscribe",
          "SNS:ListSubscriptionsByTopic",
          "SNS:Publish",
        ]
        Resource  = aws_sns_topic.alerts.arn
        Condition = { StringEquals = { "AWS:SourceOwner" = var.account_id } }
      },
      {
        Sid       = "AllowEventBridgePublish"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.alerts.arn
        # Confused-deputy guard: only rules in this account may publish here.
        Condition = { StringEquals = { "AWS:SourceAccount" = var.account_id } }
      },
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "target_5xx" {
  for_each            = var.services
  alarm_name          = "${var.name_prefix}-${each.key}-5xx-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_description   = "S34: more than 5 5xx responses/min from ${each.key} for 2 consecutive minutes."
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = each.value
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}

# S34: SPEC §5.33.4 targets "General API P95 near one second" - the threshold below is
# deliberately *not* 1s. A real local k6 run of 150 concurrent learning sessions
# (load-tests/k6/learning_sessions.js) measured ~2.9s P95 against this exact
# architecture's current shape (one ECS task, one uvicorn worker process, no autoscaling
# until this session's own aws_appautoscaling_target addition) - an alarm set at the
# SPEC's aspirational 1s would fire continuously against already-known, already-
# documented baseline behavior, not real degradation, which trains the one human who'd
# see it to ignore the alarm. 3s (a full second above the measured real baseline) fires
# on genuine regressions instead; closing the gap to the real ~1s target is the new
# CPU-based autoscaling's job (more concurrent capacity under load), not a smaller alarm
# threshold. See DECISIONS.md's S34 entry.
#
# S43 (AUD-X-13): 3s stopped being right for chat-api, and the threshold is now per-service.
# S34 calibrated it against a corpus where chat turns refused early and completed in ~1.6s.
# With a real corpus and a working reranker (D-115), a *healthy* grounded turn is four
# sequential model calls measuring p50 ~10s / p95 ~16s - so this alarm's steady state during
# normal use was ALARM. That is not merely alarm fatigue on the one monitored inbox: it is
# criterion 8's evidence alarm, which could therefore not tell an incident from a
# conversation, and `deploy-staging.yml`'s canary bake rolls both services back when any of
# these four alarms is in ALARM - so a deploy overlapping real usage would auto-roll-back a
# good release and look like a failed deploy rather than a mis-set number.
#
# chat-api moves to 20s (25% headroom over the measured p95, user decision - the same number
# recorded as criterion 7's live-staging threshold, set once from one measurement rather than
# twice by two guesses). learning-api stays at 3s: nothing has re-measured it, and its
# requests are not model calls.
#
# The scale-*out* alarm in modules/ecs-service stays at 3s deliberately and is NOT this
# number. A sensitive scaling signal and an insensitive paging signal on the same metric is
# the point of having two alarms: capacity should react long before a human is woken
# (D-113 §2).
resource "aws_cloudwatch_metric_alarm" "target_latency_p95" {
  for_each            = var.services
  alarm_name          = "${var.name_prefix}-${each.key}-p95-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p95"
  threshold           = lookup(var.latency_p95_alarm_thresholds, each.key, var.latency_p95_alarm_threshold_default)
  treat_missing_data  = "notBreaching"
  alarm_description   = "${each.key} P95 response time over ${lookup(var.latency_p95_alarm_thresholds, each.key, var.latency_p95_alarm_threshold_default)}s for 3 consecutive minutes (S34; per-service since S43/AUD-X-13)."
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = each.value
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}
