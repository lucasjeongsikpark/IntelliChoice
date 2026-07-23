output "task_execution_role_arn" {
  value = aws_iam_role.task_execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "github_oidc_provider_arn" {
  value = local.github_oidc_provider_arn
}

output "github_deploy_role_arn" {
  value = var.create_github_deploy_role ? aws_iam_role.github_deploy[0].arn : ""
}
