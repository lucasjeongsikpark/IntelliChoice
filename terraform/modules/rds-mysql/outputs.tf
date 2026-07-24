output "endpoint_address" {
  value = aws_db_instance.this.address
}

output "endpoint_port" {
  value = aws_db_instance.this.port
}

output "security_group_id" {
  value = aws_security_group.this.id
}

# D-092 (S33): AWS-managed secret (real automatic rotation) - see the matching, more
# detailed comment on rds-postgres/outputs.tf's identical output (S34: `one(...)` fix).
output "master_user_secret_arn" {
  value = one(aws_db_instance.this.master_user_secret[*].secret_arn)
}

output "db_name" {
  value = var.db_name
}
