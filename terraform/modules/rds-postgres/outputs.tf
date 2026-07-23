output "endpoint_address" {
  value = aws_db_instance.this.address
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "database_url_secret_arn" {
  value = aws_secretsmanager_secret.database_url.arn
}
