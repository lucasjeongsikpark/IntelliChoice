variable "name_prefix" {
  description = "Prefix applied to all resource names/tags (e.g. \"intellichoice-staging\")."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of Availability Zones to spread public/private subnets across."
  type        = number
  default     = 2
}

variable "enable_interface_endpoints" {
  description = <<-EOT
    Create VPC interface endpoints (ECR api/dkr, CloudWatch Logs, Secrets Manager,
    Bedrock runtime) plus the S3 gateway endpoint, so ECS tasks in private subnets
    never need a NAT Gateway for the calls this app actually makes (D-084: cheaper
    than NAT at this traffic level and keeps private subnets fully non-internet-routed).
  EOT
  type        = bool
  default     = true
}

variable "bedrock_runtime_endpoint_enabled" {
  description = "Include the bedrock-runtime interface endpoint (required for real Bedrock calls - see D-084). Split out so it can be toggled off if Bedrock stays mocked."
  type        = bool
  default     = true
}

variable "xray_endpoint_enabled" {
  description = <<-EOT
    Include the xray interface endpoint. Required for the OTel sidecar's `awsxray`
    exporter to reach the X-Ray API at all: S39's first traced deploy had the app
    exporting and the collector receiving, then failing every export with
    `Post "https://xray.us-east-1.amazonaws.com/TraceSegments": context deadline
    exceeded` - the same NAT-less unroutability that broke the sidecar's own image pull
    (AUD-F-10), one layer further in. Split out from `enable_interface_endpoints` and
    wired to `enable_otel_tracing` so the ~$7.30/mo is not paid when tracing is off.
  EOT
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}
