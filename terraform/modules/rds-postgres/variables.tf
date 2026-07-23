variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach Postgres on 5432 (the ECS task SG)."
  type        = list(string)
}

variable "engine_version" {
  type    = string
  default = "16.4"
}

variable "instance_class" {
  description = <<-EOT
    db.t4g.micro (Free Tier eligible) - this AWS account has Free Tier restrictions
    active (confirmed via a real CreateDBInstance rejection during S32/D-084), so a
    non-eligible class like db.t4g.small is rejected outright, not just costed
    differently. Matches the "don't scale up unnecessarily for <2,000 MAU" cost posture
    anyway; pass a larger class once real usage justifies it (prod environment).
  EOT
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  type    = number
  default = 20
}

variable "max_allocated_storage_gb" {
  description = "Storage autoscaling ceiling."
  type        = number
  default     = 100
}

variable "multi_az" {
  description = "Staging defaults to single-AZ (D-084's cost posture); set true for a prod environment."
  type        = bool
  default     = false
}

variable "db_name" {
  type    = string
  default = "intellichoice"
}

variable "master_username" {
  type    = string
  default = "intellichoice"
}

variable "backup_retention_days" {
  description = "1 day - this AWS account's Free Tier restrictions rejected 7 (S32/D-084); raise once the account's restrictions are lifted or a prod environment needs longer retention."
  type        = number
  default     = 1
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
