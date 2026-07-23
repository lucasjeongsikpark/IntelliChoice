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

variable "region" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
