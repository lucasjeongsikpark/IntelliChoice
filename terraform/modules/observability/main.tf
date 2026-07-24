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
resource "aws_cloudwatch_metric_alarm" "target_latency_p95" {
  for_each            = var.services
  alarm_name          = "${var.name_prefix}-${each.key}-p95-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p95"
  threshold           = 3
  treat_missing_data  = "notBreaching"
  alarm_description   = "S34: ${each.key} P95 response time over 3s for 3 consecutive minutes."
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = each.value
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}
