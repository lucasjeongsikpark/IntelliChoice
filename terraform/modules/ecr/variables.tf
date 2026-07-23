variable "repository_names" {
  description = "ECR repository names to create, e.g. [\"learning-api\", \"chat-api\"]."
  type        = list(string)
}

variable "untagged_image_expiry_days" {
  description = "Days after which untagged images are expired by the lifecycle policy."
  type        = number
  default     = 7
}

variable "tags" {
  type    = map(string)
  default = {}
}
