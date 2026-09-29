variable "name_prefix" {
  description = "Prefix applied to all resource names (e.g. \"intellichoice-staging\")."
  type        = string
}

variable "account_id" {
  description = "This account's id: scopes the Lambda role's trust policy (confused-deputy guard) and the service ARNs."
  type        = string
}

variable "region" {
  description = "Region of the ECS services, for their ARNs."
  type        = string
}

variable "secret_arns" {
  description = "The RDS-managed master secrets whose RotationSucceeded event triggers the restart (Postgres and MySQL)."
  type        = list(string)
}

variable "ecs_cluster_name" {
  description = "Cluster the API services run in."
  type        = string
}

variable "ecs_cluster_arn" {
  description = "The same cluster's ARN - checked against the name so the policy's service ARNs cannot point elsewhere."
  type        = string
}

variable "service_names" {
  description = "ECS services to force a new deployment of. Both API services: each holds both databases' credentials."
  type        = list(string)
}

variable "pass_role_arns" {
  description = "Task execution and task role ARNs the forced deployment needs iam:PassRole for."
  type        = list(string)
}

variable "alerts_topic_arn" {
  description = "The paging SNS topic (D-401) - a failed restart is the D-455 outage."
  type        = string
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}
