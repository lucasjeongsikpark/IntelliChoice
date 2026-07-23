variable "name_prefix" {
  type = string
}

variable "app_name" {
  description = "e.g. \"learning\" or \"chat\" - used in resource names/tags."
  type        = string
}

variable "api_path_patterns" {
  description = "Path patterns routed to the ALB origin instead of the S3 frontend, e.g. [\"/learning/*\"]. Must match the app's own router prefixes so no code change was needed for same-origin routing (see D-084)."
  type        = list(string)
}

variable "alb_dns_name" {
  type = string
}

variable "price_class" {
  description = "PriceClass_100 (US/EU/Canada only) is the cheapest tier - reasonable for a US-based product (D-084's cost posture)."
  type        = string
  default     = "PriceClass_100"
}

variable "tags" {
  type    = map(string)
  default = {}
}
