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

variable "tags" {
  type    = map(string)
  default = {}
}
