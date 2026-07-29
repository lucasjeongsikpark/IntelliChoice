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

variable "tags" {
  type    = map(string)
  default = {}
}

variable "account_id" {
  description = "This account's id, used in the SNS topic policy's SourceOwner/SourceAccount conditions."
  type        = string
}
