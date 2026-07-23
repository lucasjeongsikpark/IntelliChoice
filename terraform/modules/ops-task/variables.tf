variable "name_prefix" {
  type = string
}

variable "image" {
  description = "Full ECR image URI including tag - reuses the learning-api image (has every workspace package installed, including packages/db's Alembic config and the MySQL seed script)."
  type        = string
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "execution_role_arn" {
  type = string
}

variable "task_role_arn" {
  type = string
}

variable "environment" {
  type    = map(string)
  default = {}
}

variable "secrets" {
  type    = map(string)
  default = {}
}

variable "region" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}
