# ---------------------------------------------------------------------------------------
# D-213: a dashboard, because the alarms in main.tf answer "is it broken" and the question
# actually asked was "how is it going".
#
# **Why metric filters and not just infrastructure metrics.** ECS CPU and ALB latency say
# nothing about the failures this system actually has. Every real incident this session was
# invisible at that level:
#
#   - `memory_consolidation` spent 61.5 s per call and had never once succeeded in fourteen
#     days. CPU was flat; the request returned 200.
#   - The authoring batch reported `circuit_open` fourteen times and $0.00 spent. No
#     infrastructure metric moved at all.
#   - A model the account cannot invoke returns `AccessDeniedException`, which reaches the
#     caller as a tripped breaker.
#
# The application already logs all of this as structured JSON - `bedrock_call` with
# `cost_cents`/`duration_ms`/`task`, and `bedrock_call_failed` with `reason`. Metric filters
# turn those lines into metrics without adding an agent, a sidecar, or a dependency.
#
# **Cost.** Metric filters are billed per custom metric, not per log line scanned, and these
# create four. The alternative (Logs Insights queries on a dashboard) is billed per GB
# scanned on every refresh, which is a running cost that grows with log volume.
# ---------------------------------------------------------------------------------------

locals {
  # A namespace per service rather than one namespace with a `service` dimension.
  #
  # CloudWatch requires a metric-filter dimension *value* to be a JSON selector into the
  # log event (`$.task`), so a literal service name is rejected outright - the service is
  # not in the log line, it is the log group. Encoding it in the namespace is the
  # supported way to say it, and it has a second benefit: with no dimensions the count
  # filters may declare `default_value`, so a quiet period reads as a real zero rather
  # than as a gap that looks the same as "no data collected".
  metric_namespace = { for name in keys(var.log_group_names) : name => "IntelliChoice/${var.name_prefix}/${name}" }
}

# Spend. The user's standing rule is that cost bugs are production bugs, and until now the
# only way to know what Bedrock cost was to read the logs by hand.
resource "aws_cloudwatch_log_metric_filter" "bedrock_cost" {
  for_each       = var.log_group_names
  name           = "${var.name_prefix}-${each.key}-bedrock-cost-cents"
  log_group_name = each.value
  # `$.cost_cents = *` rather than a bare event match: it selects only lines that actually
  # carry the field, so a schema change shows up as a flat line instead of as zeros.
  pattern = "{ $.event = \"bedrock_call\" && $.cost_cents = * }"

  metric_transformation {
    name      = "BedrockCostCents"
    namespace = local.metric_namespace[each.key]
    value     = "$.cost_cents"
    unit      = "None"
  }
}

# Latency of the model calls themselves, separate from ALB latency - a slow turn is usually
# a slow model call, and the two were previously indistinguishable from outside.
resource "aws_cloudwatch_log_metric_filter" "bedrock_duration" {
  for_each       = var.log_group_names
  name           = "${var.name_prefix}-${each.key}-bedrock-duration-ms"
  log_group_name = each.value
  pattern        = "{ $.event = \"bedrock_call\" && $.duration_ms = * }"

  metric_transformation {
    name      = "BedrockCallDurationMs"
    namespace = local.metric_namespace[each.key]
    value     = "$.duration_ms"
    unit      = "Milliseconds"
  }
}

# Failures. `bedrock_call_failed` is logged at WARNING and the request often still returns
# 200 - by design, because the degraded paths fall back rather than erroring. That is
# exactly why it needs its own metric: nothing downstream reports it.
resource "aws_cloudwatch_log_metric_filter" "bedrock_failed" {
  for_each       = var.log_group_names
  name           = "${var.name_prefix}-${each.key}-bedrock-call-failed"
  log_group_name = each.value
  pattern        = "{ $.event = \"bedrock_call_failed\" }"

  metric_transformation {
    name = "BedrockCallFailed"
    # A real zero when nothing failed, so the panel shows a line on the axis instead of a
    # gap - and "no failures" stops looking identical to "no data reaching CloudWatch".
    namespace     = local.metric_namespace[each.key]
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

# The breaker specifically, split out from failures. An open circuit means calls are being
# refused *without being attempted*, which reads as "nothing is happening" in every other
# view - the authoring batch's fourteen skipped candidates and $0.00 spend.
resource "aws_cloudwatch_log_metric_filter" "bedrock_circuit_open" {
  for_each       = var.log_group_names
  name           = "${var.name_prefix}-${each.key}-bedrock-circuit-open"
  log_group_name = each.value
  pattern        = "{ $.event = \"bedrock_call_failed\" && $.reason = \"circuit_open\" }"

  metric_transformation {
    name          = "BedrockCircuitOpen"
    namespace     = local.metric_namespace[each.key]
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name_prefix}-overview"

  dashboard_body = jsonencode({
    widgets = concat(
      [
        {
          type   = "text"
          x      = 0
          y      = 0
          width  = 24
          height = 2
          properties = {
            markdown = join("\n", [
              "# ${var.name_prefix} — service overview",
              "Model-call panels come from structured application logs (`bedrock_call`, `bedrock_call_failed`), not from infrastructure metrics — every incident so far was invisible in CPU and ALB latency. **No failure line *and* no spend line means calls are not being attempted at all** — which is what an open circuit looks like, and is invisible in CPU or latency.",
            ])
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 2
          width  = 12
          height = 6
          properties = {
            title  = "Bedrock spend (cents, 5 min)"
            region = data.aws_region.current.name
            view   = "timeSeries"
            stat   = "Sum"
            period = 300
            metrics = [
              for name in keys(var.log_group_names) :
              [local.metric_namespace[name], "BedrockCostCents", { label = name }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 2
          width  = 12
          height = 6
          properties = {
            title  = "Model call failures and open circuits"
            region = data.aws_region.current.name
            view   = "timeSeries"
            stat   = "Sum"
            period = 300
            yAxis  = { left = { min = 0 } }
            metrics = concat(
              [for name in keys(var.log_group_names) : [local.metric_namespace[name], "BedrockCallFailed", { label = "${name} failed" }]],
              [for name in keys(var.log_group_names) : [local.metric_namespace[name], "BedrockCircuitOpen", { label = "${name} circuit open" }]]
            )
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 8
          width  = 12
          height = 6
          properties = {
            title  = "Model call duration p50/p95/max (ms)"
            region = data.aws_region.current.name
            view   = "timeSeries"
            period = 300
            # A ceiling being hit looks like a flat line at the timeout, which is how the
            # 61.5 s consolidation call was identified - p95 and max together make that
            # shape visible where an average would not.
            # `concat` of three per-stat lists, deliberately **not** `flatten`. CloudWatch
            # wants a list of lists (each inner list is one metric), and `flatten` removes
            # every level of nesting - it dissolved each metric into loose strings and the
            # API rejected the body with `Field "metrics" has to be an array of array of
            # strings`.
            metrics = concat(
              [for name in keys(var.log_group_names) : [local.metric_namespace[name], "BedrockCallDurationMs", { stat = "p50", label = "${name} p50" }]],
              [for name in keys(var.log_group_names) : [local.metric_namespace[name], "BedrockCallDurationMs", { stat = "p95", label = "${name} p95" }]],
              [for name in keys(var.log_group_names) : [local.metric_namespace[name], "BedrockCallDurationMs", { stat = "Maximum", label = "${name} max" }]],
            )
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 8
          width  = 12
          height = 6
          properties = {
            title  = "ALB request rate and 5xx"
            region = data.aws_region.current.name
            view   = "timeSeries"
            stat   = "Sum"
            period = 300
            metrics = concat(
              [["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix]],
              [for name, suffix in var.services : ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "TargetGroup", suffix, "LoadBalancer", var.alb_arn_suffix, { label = "${name} 5xx" }]]
            )
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 14
          width  = 12
          height = 6
          properties = {
            title  = "Request latency p95 (s)"
            region = data.aws_region.current.name
            view   = "timeSeries"
            stat   = "p95"
            period = 300
            metrics = [
              for name, suffix in var.services :
              ["AWS/ApplicationELB", "TargetResponseTime", "TargetGroup", suffix, "LoadBalancer", var.alb_arn_suffix, { label = name }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 14
          width  = 12
          height = 6
          properties = {
            title  = "Running tasks"
            region = data.aws_region.current.name
            view   = "timeSeries"
            stat   = "Average"
            period = 300
            metrics = [
              for name in keys(var.services) :
              ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.ecs_cluster_name, "ServiceName", name, { label = name }]
            ]
          }
        },
      ],
      # The failure lines themselves, in the same place. A count tells you something broke;
      # only the line says what. Logs Insights widgets are billed per GB scanned when the
      # dashboard loads, so this is one query over one hour rather than several.
      [
        {
          type   = "log"
          x      = 0
          y      = 20
          width  = 24
          height = 6
          properties = {
            title  = "Recent model-call failures"
            region = data.aws_region.current.name
            query = join(" ", [
              "SOURCE '${try(values(var.log_group_names)[0], "")}'",
              "| fields @timestamp, task, reason, detail, attempts, duration_ms",
              "| filter event = 'bedrock_call_failed'",
              "| sort @timestamp desc",
              "| limit 20",
            ])
            view = "table"
          }
        },
      ]
    )
  })
}

data "aws_region" "current" {}
