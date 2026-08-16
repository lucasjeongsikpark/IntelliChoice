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

# D-213: the log groups the model-call metric filters are attached to, service name ->
# log group name. Keys should match `services`, but this is deliberately a separate
# variable rather than being folded into it: `services` maps to ALB target groups, and a
# worker with no load balancer (ops-task) still emits `bedrock_call` lines worth counting.
variable "log_group_names" {
  description = "Map of service name -> CloudWatch log group name, for the model-call metric filters."
  type        = map(string)
  default     = {}
}

# --- D-244 ----------------------------------------------------------------------------

variable "database_instances" {
  description = <<-EOT
    RDS instances to alarm on, keyed by short name. `identifier` is the
    `DBInstanceIdentifier` dimension; `allocated_storage_gb` sets the free-storage
    threshold relative to the volume rather than as a fixed number of bytes, so resizing
    the instance cannot silently turn the alarm into a no-op. `max_connections_alarm` is
    per-engine because the two instance classes do not share a connection ceiling.
  EOT
  type = map(object({
    identifier            = string
    allocated_storage_gb  = number
    max_connections_alarm = number
  }))
  default = {}
}

variable "ecs_memory_alarm_mib" {
  description = <<-EOT
    MemoryUtilized (MiB) above which an ECS service alarms. Set below the task's hard
    memory limit with room to act: the point is to fire *before* the OOM kill, since the
    kill itself only becomes visible later as an unexplained 5xx burst.
  EOT
  type        = number
  default     = 700
}

variable "bedrock_hourly_spend_alarm_cents" {
  description = <<-EOT
    Bedrock spend in one hour, in cents, above which a service alarms. Calibrated from
    measured runs rather than guessed: D-240 spent 64 cents on a 22-candidate batch and
    D-243 spent 59 across five, both of which are *offline pipeline* runs rather than
    serving traffic. A serving hour costing more than this has no benign explanation.
  EOT
  type        = number
  default     = 200
}

variable "ops_task_log_group" {
  description = <<-EOT
    Log group of the ECS ops task, where the offline question-generation pipeline and the
    curriculum loader write their records (D-244). Separate from `log_group_names` because
    the same `bedrock_call` event name appears in both, and a batch's spend is not a
    student's session cost.
  EOT
  type        = string
}

# --- D-377: the application-layer alarms ------------------------------------------------

variable "client_error_alarm_threshold" {
  description = <<-EOT
    Browser crash reports in 15 minutes above which to alert. Deliberately low - a render
    crash is not a rate to be tuned, and `ErrorBoundary` fires once per failed render so a
    loop is already bounded by the endpoint's own per-caller limit.
  EOT
  type        = number
  default     = 0
}

variable "background_failure_alarm_threshold" {
  description = <<-EOT
    `background_*_failed` events in one hour above which to alert. Above zero because a
    single transient Bedrock failure is absorbed by design and the student still gets
    reviewed content; D-329's undetected incident ran at ~2.4/hour sustained.
  EOT
  type        = number
  default     = 2
}

variable "daily_completed_sessions_floor" {
  description = <<-EOT
    Completed learning sessions in 24h below which to alert, or 0 to disable. A floor rather
    than a target: it should fire when the number is implausibly low for a whole day, not
    when it dips. Set to 0 while staging traffic is synthetic and there is no honest floor.
  EOT
  type        = number
  default     = 0
}

variable "nightly_job_events" {
  description = <<-EOT
    Job names whose `<name>_job_complete` record is metric-filtered and heartbeat-alarmed.
    Must match the `job` field the CLIs emit.
  EOT
  type        = list(string)
  default     = []
}
