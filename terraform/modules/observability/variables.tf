variable "name_prefix" {
  type = string
}

variable "monthly_budget_usd" {
  description = <<-EOT
    Account-level spend ceiling backstop (D-084) - the app's own Bedrock gateway only
    enforces a per-session (~$0.50) and per-student-per-day (learning-api chat, $1.00)
    ceiling; nothing existing catches runaway spend across the whole account.
  EOT
  type        = number
  default     = 20
}

variable "notification_email" {
  description = "Email address to notify when the budget threshold/forecast is exceeded."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
