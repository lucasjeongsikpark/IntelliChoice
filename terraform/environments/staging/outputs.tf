output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}

output "alb_dns_name" {
  value = module.alb.alb_dns_name
}

output "postgres_endpoint" {
  value = module.rds_postgres.endpoint_address
}

output "mysql_endpoint" {
  value = module.rds_mysql.endpoint_address
}

output "ops_task_definition_arn" {
  value = module.ops_task.task_definition_arn
}

output "ops_task_log_group" {
  value = module.ops_task.log_group_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_tasks_security_group_id" {
  value = aws_security_group.ecs_tasks.id
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "cloudfront_learning_domain" {
  value = module.cloudfront_learning.distribution_domain_name
}

output "cloudfront_chat_domain" {
  value = module.cloudfront_chat.distribution_domain_name
}

output "cloudfront_learning_bucket" {
  value = module.cloudfront_learning.bucket_name
}

output "cloudfront_chat_bucket" {
  value = module.cloudfront_chat.bucket_name
}

output "cloudfront_learning_distribution_id" {
  value = module.cloudfront_learning.distribution_id
}

output "cloudfront_chat_distribution_id" {
  value = module.cloudfront_chat.distribution_id
}
