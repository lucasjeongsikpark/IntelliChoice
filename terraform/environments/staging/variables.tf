variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "name_prefix" {
  type    = string
  default = "intellichoice-staging"
}

variable "notification_email" {
  description = "Receives the AWS Budget alarm notifications (D-084)."
  type        = string
}

variable "github_org" {
  description = "GitHub org/user the deploy-staging.yml workflow runs from - scopes the OIDC deploy role's trust policy. Empty until the repo exists (see iam module's create_github_oidc_provider/create_github_deploy_role)."
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repo name (without org prefix) the deploy-staging.yml workflow runs from."
  type        = string
  default     = ""
}

# Bootstrapping note: these default to a placeholder that is never actually deployed -
# the very first applies (vpc/ecr/iam/rds) are run with `-target` before any image
# exists in ECR at all (see the S32/D-084 execution order). Override with the real tag
# via `-var` once `docker build`/`ECR push` has happened.
variable "learning_api_image_tag" {
  type    = string
  default = "unset"
}

variable "chat_api_image_tag" {
  type    = string
  default = "unset"
}

# "mock" until the real Bedrock model-access agreement is confirmed AVAILABLE and a
# direct smoke test has passed (D-025/D-084) - flip to "bedrock" via `-var` once verified.
variable "bedrock_provider" {
  type    = string
  default = "mock"
}

variable "bedrock_tutor_model_id" {
  type    = string
  default = "anthropic.claude-sonnet-5"
}

variable "bedrock_embedding_model_id" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}

# App-level LEARNING_ENVIRONMENT/CHAT_ENVIRONMENT (not this Terraform environment's own
# name, which stays "staging" throughout - see name_prefix/local.common_tags). Controls
# app-code-level behavior gated on `environment=="dev"`, most notably `POST /dev/token`
# (both apps' dev-only stand-in for real go.intellichoice.org auth - 404s outside "dev"
# by design, per its own docstring: "must never exist as reachable surface in a real
# deployment"). Defaults to "staging" (backdoor disabled); the user explicitly asked for
# it enabled on this staging deployment specifically, to test authenticated flows
# through the browser without real auth integration (S32/D-084) - set via
# terraform.tfvars, not this default, so the default stays the safer posture.
variable "app_environment" {
  type    = string
  default = "staging"
}

# S39 (AUD-F): turns on distributed tracing for both services - the aws-otel-collector
# sidecar plus `*_OTEL_ENABLED=true`. Both halves are needed together: the flag alone
# exports OTLP into nothing (which is the state S38 found and could not evidence against,
# D-102), and the sidecar alone collects nothing.
#
# Defaults true because §2.6 criterion 9 requires the PII floor to be verified against
# live staging *traces*, and an audit criterion that depends on someone remembering to set
# a flag is not a criterion. Costs: one small sidecar per task plus X-Ray ingest, both
# negligible at this scale - X-Ray's free tier covers 100k traces/month.
variable "enable_otel_tracing" {
  type    = bool
  default = true
}

# Pinned, and pinned in two places on purpose: this value and the `VERSION` that
# scripts/mirror-otel-collector.sh pushed must agree, or the deploy fails at image pull.
# ECR's IMMUTABLE tag policy means a given version tag always means the same image.
variable "otel_collector_version" {
  type    = string
  default = "v0.43.3"
}

locals {
  common_tags = {
    Project     = "IntelliChoice"
    Environment = "staging"
    ManagedBy   = "terraform"
  }
}
