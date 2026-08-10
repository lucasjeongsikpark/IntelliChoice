variable "name_prefix" {
  type = string
}

variable "secret_arns" {
  description = "Secrets Manager secret ARNs the shared task execution role may read (injected into containers via the task definition's `secrets` block)."
  type        = list(string)
}

variable "bedrock_model_arns" {
  description = "Bedrock foundation-model/inference-profile ARNs the shared task role may invoke via bedrock:InvokeModel - both TitanEmbeddingProvider's invoke_model calls and AnthropicBedrockProvider's converse calls (classic bedrock-runtime, see D-084)."
  type        = list(string)
}

variable "log_group_arns" {
  description = "CloudWatch Log Group ARNs the shared task execution role may write to."
  type        = list(string)
}

variable "create_github_oidc_provider" {
  description = <<-EOT
    Whether to create the GitHub Actions OIDC identity provider. AWS accounts should
    have at most one - set false if one already exists (check with
    `aws iam list-open-id-connect-providers` before applying) and pass its ARN via
    github_oidc_provider_arn instead.
  EOT
  type        = bool
  default     = false
}

variable "github_oidc_provider_arn" {
  description = "Existing GitHub OIDC provider ARN to reuse when create_github_oidc_provider is false."
  type        = string
  default     = ""
}

variable "create_github_deploy_role" {
  description = "Whether to create the GitHub Actions deploy role. Requires github_org/github_repo (the repo must exist so the trust condition is correct)."
  type        = bool
  default     = false
}

variable "github_org" {
  type    = string
  default = ""
}

variable "github_repo" {
  type    = string
  default = ""
}

variable "deploy_role_permissions_boundary_arn" {
  description = "Optional permissions-boundary ARN for the GitHub deploy role. Empty = none."
  type        = string
  default     = ""
}

variable "ecr_repository_arns" {
  description = "ECR repository ARNs the GitHub deploy role may push images to."
  type        = list(string)
  default     = []
}

variable "ecs_cluster_arn" {
  description = "ECS cluster ARN the GitHub deploy role may update services / run tasks in."
  type        = string
  default     = ""
}

variable "frontend_bucket_arns" {
  description = "S3 frontend bucket ARNs the GitHub deploy role may sync built assets to."
  type        = list(string)
  default     = []
}

variable "cloudfront_distribution_arns" {
  description = "CloudFront distribution ARNs the GitHub deploy role may invalidate after a frontend deploy."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "metrics_log_group_arns" {
  description = <<-EOT
    CloudWatch Log Group ARNs the shared ECS *task* role may write Embedded Metric Format
    records to (D-244). Deliberately separate from `log_group_arns`, which the *execution*
    role uses for container stdout: the collector shares the task role with the application
    container, so anything granted here is reachable from application code too. Empty
    disables the grant entirely.
  EOT
  type        = list(string)
  default     = []
}
