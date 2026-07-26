variable "name" {
  description = "Short service name, e.g. \"learning-api\"."
  type        = string
}

variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "cluster_id" {
  type = string
}

variable "listener_arn" {
  type = string
}

variable "security_group_ids" {
  description = <<-EOT
    Security group(s) for the task ENI - owned by the root module, not created here, so
    that RDS's "allow from the ECS task SG" rule and this service's "needs the DB secret
    ARN" input don't form a circular module dependency (S32/D-084).
  EOT
  type        = list(string)
}

variable "path_patterns" {
  description = "ALB listener-rule path patterns routed to this service, e.g. [\"/learning/*\"]."
  type        = list(string)
}

variable "listener_rule_priority" {
  type = number
}

variable "container_port" {
  type = number
}

variable "image" {
  description = "Full ECR image URI including tag."
  type        = string
}

variable "cpu" {
  description = "Fargate task-level vCPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 256
}

variable "memory" {
  description = "Fargate task-level memory in MiB."
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Staging default is 1 (D-084's cost posture); use 2+ for a prod environment."
  type        = number
  default     = 1
}

variable "execution_role_arn" {
  type = string
}

variable "task_role_arn" {
  type = string
}

variable "environment" {
  description = "Plain (non-secret) container environment variables."
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Container env vars sourced from Secrets Manager: { ENV_VAR_NAME = secret_arn }."
  type        = map(string)
  default     = {}
}

variable "health_check_path" {
  type    = string
  default = "/healthz"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "enable_execute_command" {
  description = "Enable ECS Exec (aws ecs execute-command) for debugging/ad-hoc in-VPC operations."
  type        = bool
  default     = false
}

variable "read_only_root_filesystem" {
  description = <<-EOT
    D-088 (S33 Fargate hardening, the ECS equivalent of SPEC §6.22's Kubernetes-shaped
    "pod security" item - this deploys to Fargate, not EKS, per D-004/D-082-084).
    Defaults true: neither learning-api nor chat-api writes to the local filesystem at
    runtime (confirmed by grep - no `tempfile`/`open(..., "w")` calls anywhere in either
    app), so a compromised process gets no writable root filesystem to persist anything
    into. Overridable per-service in case a future service genuinely needs local scratch
    space (Fargate has no `tmpfs` container-definition support the way EC2-launch-type
    ECS does - a writable need would require a real ephemeral-storage volume mount, not
    just flipping this back to false).
  EOT
  type        = bool
  default     = true
}

variable "region" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

# S34: Application Auto Scaling (Fargate's real equivalent of SPEC §5.33.4's HPA) - see
# the matching comment on `aws_appautoscaling_target`/`aws_appautoscaling_policy` in
# main.tf for the full reasoning.
variable "enable_autoscaling" {
  type    = bool
  default = true
}

variable "autoscaling_min_capacity" {
  description = "Should match var.desired_count - the floor Application Auto Scaling won't go below."
  type        = number
  default     = 1
}

variable "autoscaling_max_capacity" {
  description = "Deliberately modest (Free Tier + solo-maintainer scale, not enterprise headroom)."
  type        = number
  default     = 3
}

variable "autoscaling_cpu_target_percent" {
  type    = number
  default = 70
}

# S39 (AUD-F): the OTLP collector both apps' `OTEL_ENABLED=true` path needs.
#
# `packages/observability`'s `configure_tracing` exports OTLP/HTTP to an endpoint; locally
# that is docker-compose's `otel-collector`, and staging had no equivalent at all - which
# is why S38 could not evidence the "traces" half of its PII-floor line (D-102) and why
# §2.6 criterion 9 stayed open. Flipping `OTEL_ENABLED` without this exports into a void.
#
# Deployed as a sidecar in the same task rather than a standalone collector service: the
# app reaches it on localhost (no service discovery, no extra ALB target, no cross-task
# network hop), it scales with the app by construction, and there is one less thing for a
# solo maintainer to operate. The trade-off is that a collector restart takes the task
# with it - acceptable because traces are diagnostic, not load-bearing.
variable "enable_otel_sidecar" {
  description = "Run an aws-otel-collector sidecar exporting spans to AWS X-Ray."
  type        = bool
  default     = false
}

variable "otel_collector_image" {
  description = <<-EOT
    AWS's distro of the OpenTelemetry Collector. Pinned rather than :latest so a deploy
    cannot silently change the collector - the same reason deploy-staging.yml tags images
    by commit SHA instead of appending to a mutable tag (D-096).
  EOT
  type        = string
  default     = "public.ecr.aws/aws-observability/aws-otel-collector:v0.43.3"
}

variable "otel_collector_cpu" {
  description = "Reserved for the sidecar out of the task's total cpu/memory."
  type        = number
  default     = 128
}

variable "otel_collector_memory" {
  type    = number
  default = 256
}
