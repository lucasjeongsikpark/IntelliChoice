# D-244: alarms on the things that have actually broken in this project.
#
# **The gap this closes.** Before this file there were ten alarms, and all ten watched
# either ALB latency/5xx or the autoscaler's own task count. Meanwhile:
#
#   - D-115: the reranker was dead for a week in staging. Bedrock calls failed on every
#     request; the ALB returned 200 the whole time, because the degraded path is a
#     *successful* response with a worse answer.
#   - D-242: LangSmith rejected every run for weeks. Four Bedrock metric filters per
#     service were watching, and none of them watched telemetry delivery, so a whole leg
#     of the observability architecture was dark while every dashboard stayed green.
#   - D-240/D-243: an open Bedrock circuit turned a paid pipeline batch into fifteen
#     skipped candidates. Nothing alarms on the circuit.
#
# The pattern in all three is the same: **a failure that keeps returning 200 is invisible
# to every infrastructure alarm.** The five log-derived metrics in dashboard.tf were built
# to see exactly that class, and then nothing was ever set to fire on them - so the
# dashboard could show it, if a human happened to look.
#
# Everything here routes to the existing `aws_sns_topic.alerts`, the same inbox the ALB
# alarms use. No new notification channel: one monitored inbox that is actually read beats
# a second one that is not.

# --- The silent-failure class: model calls and telemetry ------------------------------

# An open circuit means the gateway has stopped *attempting* calls. It is the one state
# where both the failure count and the spend go to zero, so it cannot be inferred from
# either - which is why it gets its own alarm rather than a threshold on failures.
resource "aws_cloudwatch_metric_alarm" "bedrock_circuit_open" {
  for_each            = var.log_group_names
  alarm_name          = "${var.name_prefix}-${each.key}-bedrock-circuit-open"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BedrockCircuitOpen"
  namespace           = local.metric_namespace[each.key]
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  # The circuit closing produces no log line, so absence of data is the healthy state and
  # must not read as a breach - this is the difference between an alarm and a stuck alarm.
  treat_missing_data = "notBreaching"
  alarm_description = join(" ", [
    "D-244: ${each.key}'s Bedrock circuit breaker opened, so model calls are no longer",
    "being attempted. Both spend and failure count read zero while this is true, which is",
    "why neither can be used to detect it. Check `bedrock_call_failed` in /ecs/${each.key}",
    "for the failures that opened it - D-238's was an invalid model id, and the breaker",
    "made the real cause invisible.",
  ])
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}

# D-242's alarm, now with a threshold. The metric filter was added in that session; this is
# what makes it able to wake somebody.
resource "aws_cloudwatch_metric_alarm" "langsmith_ingest_failed" {
  for_each            = var.log_group_names
  alarm_name          = "${var.name_prefix}-${each.key}-langsmith-ingest-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "LangSmithIngestFailed"
  namespace           = local.metric_namespace[each.key]
  period              = 900
  statistic           = "Sum"
  # Not zero: the client logs a warning on transient network blips and retries them
  # successfully. Ten in fifteen minutes is the shape of "it is never getting through",
  # which is what D-242 actually looked like - not one bad flush.
  threshold          = 10
  treat_missing_data = "notBreaching"
  alarm_description = join(" ", [
    "D-244: ${each.key} is failing to deliver traces to LangSmith. This ran for weeks",
    "undetected (D-242) because the client retries a 403 forever at WARNING and nothing",
    "watched it. The AI-observability leg is dark while this is firing; app traffic is",
    "unaffected, so nothing else will tell you.",
  ])
  # D-401: the informational channel, and this alarm is the reason the split exists. Its own
  # description above says app traffic is unaffected - and with the LangSmith quota exhausted it
  # will sit in ALARM indefinitely, so on the page channel it would make every real alarm
  # unreadable.
  alarm_actions = [aws_sns_topic.alerts_info.arn]
  ok_actions    = [aws_sns_topic.alerts_info.arn]
  tags          = var.tags
}

# Sustained model-call failure with the circuit still closed - the D-115 shape, where every
# request succeeds at the ALB and returns a degraded answer.
resource "aws_cloudwatch_metric_alarm" "bedrock_call_failed" {
  for_each            = var.log_group_names
  alarm_name          = "${var.name_prefix}-${each.key}-bedrock-call-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "BedrockCallFailed"
  namespace           = local.metric_namespace[each.key]
  period              = 300
  statistic           = "Sum"
  # Structured-output failures are a normal, bounded part of the pipeline (D-243 measured
  # the rate and fixed the largest cause), so a low threshold would page on healthy noise.
  # Five failures in five minutes, three periods running, is a pattern rather than a blip.
  threshold          = 5
  treat_missing_data = "notBreaching"
  alarm_description = join(" ", [
    "D-244: ${each.key} has been failing Bedrock calls for 15 minutes with the circuit",
    "still closed. Requests keep returning 200 with degraded answers, so ALB 5xx and",
    "latency will both look healthy - this is the D-115 shape that went a week unnoticed.",
  ])
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}

# --- AWS resources that were collecting metrics nobody watched ------------------------

# 160 RDS metrics were being collected and zero alarms read any of them. Postgres holds
# every session, checkpoint and question row; MySQL is the read-only profile adapter.
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  for_each            = var.database_instances
  alarm_name          = "${var.name_prefix}-${each.key}-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"
  alarm_description   = "D-244: ${each.key} above 80% CPU for 15 minutes."
  dimensions          = { DBInstanceIdentifier = each.value.identifier }
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}

# **The one that turns into an outage rather than a slowdown.** A full disk stops writes
# entirely, and RDS storage autoscaling has a cooldown - so the useful alarm fires with
# enough headroom to act, not at the moment it is already full. 20% of allocated.
resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  for_each            = var.database_instances
  alarm_name          = "${var.name_prefix}-${each.key}-free-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Minimum"
  threshold           = each.value.allocated_storage_gb * 1024 * 1024 * 1024 * 0.2
  # `missing` and not `notBreaching`: an instance that has stopped reporting free storage
  # is not thereby known to have plenty, and this is the alarm whose false-negative ends
  # in a database that cannot accept writes.
  treat_missing_data = "missing"
  alarm_description = join(" ", [
    "D-244: ${each.key} is below 20% free storage. A full RDS volume rejects writes",
    "outright - this is an outage, not a slowdown - and storage autoscaling has a cooldown,",
    "so this threshold is set to leave room to act rather than to report the fact.",
  ])
  dimensions    = { DBInstanceIdentifier = each.value.identifier }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}

# Connection exhaustion presents as request timeouts with healthy CPU, which reads on every
# existing alarm as a latency problem and sends you to the wrong place.
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  for_each            = var.database_instances
  alarm_name          = "${var.name_prefix}-${each.key}-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Maximum"
  threshold           = each.value.max_connections_alarm
  treat_missing_data  = "notBreaching"
  alarm_description = join(" ", [
    "D-244: ${each.key} connection count is high. This presents as request timeouts with",
    "normal CPU, so the latency alarms will point at the application rather than here.",
  ])
  dimensions    = { DBInstanceIdentifier = each.value.identifier }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}

# Container Insights has been on since S32 and nothing read it either. Memory matters more
# than CPU here: the app container ends up OOM-killed and restarted, which shows up as a
# brief 5xx burst long after the memory pressure that caused it.
resource "aws_cloudwatch_metric_alarm" "ecs_memory" {
  for_each            = var.services
  alarm_name          = "${var.name_prefix}-${each.key}-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "MemoryUtilized"
  namespace           = "ECS/ContainerInsights"
  period              = 300
  statistic           = "Average"
  threshold           = var.ecs_memory_alarm_mib
  treat_missing_data  = "notBreaching"
  alarm_description = join(" ", [
    "D-244: ${each.key} memory is high. An OOM kill surfaces later as a short 5xx burst",
    "with no other explanation, so this is the signal that arrives in time to be useful.",
  ])
  dimensions    = { ClusterName = var.ecs_cluster_name, ServiceName = "${var.name_prefix}-${each.key}" }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}

# --- Cost -----------------------------------------------------------------------------

# The monthly AWS budget in main.tf is a *billing* control and reports at day granularity.
# It cannot see a Bedrock spend anomaly inside an afternoon, which is the shape a runaway
# retry loop or a stuck agent produces - and which this project treats as a production bug.
resource "aws_cloudwatch_metric_alarm" "bedrock_spend_spike" {
  for_each            = var.log_group_names
  alarm_name          = "${var.name_prefix}-${each.key}-bedrock-spend-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BedrockCostCents"
  namespace           = local.metric_namespace[each.key]
  period              = 3600
  statistic           = "Sum"
  threshold           = var.bedrock_hourly_spend_alarm_cents
  treat_missing_data  = "notBreaching"
  alarm_description = join(" ", [
    "D-244: ${each.key} spent more than ${var.bedrock_hourly_spend_alarm_cents} cents on",
    "Bedrock in one hour. The monthly AWS budget reports at day granularity and cannot see",
    "an afternoon-shaped anomaly. Treat a cost spike as a production bug, not a bill.",
  ])
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}
