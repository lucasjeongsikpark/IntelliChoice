variable "name_prefix" {
  type = string
}

variable "monthly_budget_usd" {
  description = <<-EOT
    Account-level spend ceiling backstop (D-084) - the app's own Bedrock gateway only
    enforces a per-session (~$0.50) and per-student-per-day (learning-api chat, $1.00)
    ceiling; nothing existing catches runaway spend across the whole account.
  EOT
  type        = number
  default     = 20
}

variable "notification_email" {
  description = "Email address to notify when the budget threshold/forecast is exceeded."
  type        = string
}

# S34: per-service CloudWatch alarms (5xx rate + P95 latency) - the rollback-trigger gate
# deploy-staging.yml's canary bake period polls, and general standing alerting via the
# same SNS topic the budget alarm already emails (var.notification_email).
variable "alb_arn_suffix" {
  type = string
}

variable "services" {
  description = "Map of service name -> ALB target-group ARN suffix to alarm on."
  type        = map(string)
}

# S43 (AUD-X-13): the paging alarm's threshold is per-service, because "too slow" is not
# one number across two products. A learning-api request is a database read; a grounded
# chat turn is four sequential model calls. See the alarm resource for the full rationale.
variable "latency_p95_alarm_threshold_default" {
  description = "Seconds of ALB p95 TargetResponseTime above which the paging alarm fires, for services with no explicit override."
  type        = number
  default     = 3
}

variable "latency_p95_alarm_thresholds" {
  description = "Per-service overrides for the paging alarm threshold, in seconds. Keys must match `services`."
  type        = map(number)
  default     = {}
}

# AUD-F-33: learning-api scaled out to 3 tasks and then sat there for over two hours with
# its own scale-in alarm in ALARM the whole time and no scaling activity recorded. Nothing
# alarmed on it; it only surfaced because a measurement needed the capacity to hold still.
# A service that scales out reliably and scales in unreliably has a cost floor set by its
# worst recent minute, and on the pilot's usage pattern (school hours, then idle) that is
# the common case rather than the corner.
variable "ecs_cluster_name" {
  description = "ECS cluster the alarmed services run in, for the ContainerInsights dimension."
  type        = string
  default     = ""
}

variable "capacity_floors" {
  description = <<-EOT
    Per-service capacity floor to alarm above, as `{ ecs_service_name, min_capacity }`.
    The service name is passed explicitly rather than derived from the key, because an
    alarm whose dimension is assembled by string convention reports "insufficient data"
    when the convention changes - which is indistinguishable from a healthy service and is
    exactly the false negative AUD-F-12 was. Empty disables the alarm.
  EOT
  type = map(object({
    ecs_service_name = string
    min_capacity     = number
  }))
  default = {}
}

variable "capacity_floor_alarm_minutes" {
  description = <<-EOT
    Minutes a service may sit above its floor before this alarms. Must clear a *legitimate*
    scale-in: the scale-in alarm needs 15 quiet minutes and its policy then has a 300 s
    cooldown, so normal behaviour can hold extra capacity for ~20 minutes after traffic
    stops. 60 is three times that, and well under the 84+ minutes AUD-F-33 observed.
  EOT
  type        = number
  default     = 60
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "account_id" {
  description = "This account's id, used in the SNS topic policy's SourceOwner/SourceAccount conditions."
  type        = string
}
