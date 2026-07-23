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
  description = "Security groups allowed to reach MySQL on 3306 (the ECS task SG)."
  type        = list(string)
}

variable "engine_version" {
  type    = string
  default = "8.4.10" # 8.4.3 doesn't exist on RDS - confirmed via `aws rds describe-db-engine-versions`
}

variable "instance_class" {
  description = <<-EOT
    This instance imitates go.intellichoice.org's shape for staging (D-082/D-083/D-084) -
    it is not the real external system, just IntelliChoice's own seeded fixture DB, so it
    stays on the smallest practical class rather than matching the Postgres instance's sizing.
  EOT
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  type    = number
  default = 20
}

variable "multi_az" {
  type    = bool
  default = false
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
  type    = number
  default = 1
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
