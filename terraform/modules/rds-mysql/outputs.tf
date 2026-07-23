output "endpoint_address" {
  value = aws_db_instance.this.address
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "mysql_url_secret_arn" {
  value = aws_secretsmanager_secret.mysql_url.arn
}

output "db_name" {
  value = var.db_name
}
