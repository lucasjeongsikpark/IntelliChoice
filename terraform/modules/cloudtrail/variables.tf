variable "name_prefix" {
  description = "Environment name prefix, e.g. \"intellichoice-staging\"."
  type        = string
}

variable "aws_region" {
  description = "Region the trail is created in. Management events are still captured in every region (is_multi_region_trail), but the trail resource itself is regional and its ARN is used in the bucket policy's aws:SourceArn condition."
  type        = string
}

variable "log_retention_days" {
  description = "Days before delivered log objects (and their noncurrent versions) expire. The trail itself is free; S3 storage is not, and an unpruned audit bucket is how a free feature becomes a bill. 90 matches the console's own management-event history window and this project's other 90-day retention boundaries."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
