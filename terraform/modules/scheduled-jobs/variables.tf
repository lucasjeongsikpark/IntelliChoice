variable "name_prefix" {
  description = "Prefix applied to all resource names/tags (e.g. \"intellichoice-staging\")."
  type        = string
}

variable "account_id" {
  description = "This account's id, used to scope the Scheduler role's trust policy to it (confused-deputy guard)."
  type        = string
}

variable "ecs_cluster_arn" {
  description = "Cluster the scheduled tasks run in."
  type        = string
}

variable "ops_task_definition_arn_prefix" {
  description = <<-EOT
    The ops-task definition ARN **without** a revision suffix
    (e.g. arn:aws:ecs:…:task-definition/intellichoice-staging-ops-task). Deliberately not
    revision-pinned: `deploy-staging.yml` registers a new revision on every deploy, so a
    pinned schedule would keep running an increasingly stale image, and a `ecs:RunTask`
    policy pinned to one revision would start denying after the next deploy.
  EOT
  type        = string
}

variable "ops_container_name" {
  description = "Container name inside the ops task definition, for the command override."
  type        = string
}

variable "ops_task_log_group" {
  description = "CloudWatch log group the ops task writes to, quoted in the failure notification."
  type        = string
}

variable "pass_role_arns" {
  description = "Task execution and task role ARNs that RunTask needs iam:PassRole for."
  type        = list(string)
}

variable "subnet_ids" {
  description = "Private subnets to run the scheduled tasks in."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group for the scheduled tasks (the shared ECS tasks SG)."
  type        = string
}

variable "alerts_topic_arn" {
  description = "SNS topic that failure notifications go to - the same one the CloudWatch alarms use."
  type        = string
}

variable "enabled" {
  description = <<-EOT
    Whether the schedules are ENABLED. Kept as a variable rather than hardcoded because
    §2.6 criterion 6 needs an uninterrupted >= 1 week of unattended runs: if something has
    to be paused, it should be one explicit flag flip that is visible in a diff, not three
    console clicks nobody records.
  EOT
  type        = bool
  default     = true
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}
