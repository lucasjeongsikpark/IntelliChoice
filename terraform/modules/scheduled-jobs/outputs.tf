output "schedule_names" {
  description = "Every schedule created, so criterion 6's evidence can be gathered by name rather than by console browsing."
  value       = [for s in aws_scheduler_schedule.job : s.name]
}

output "schedule_expressions" {
  description = "job name -> cron expression (UTC), for the record in PROGRESS.md."
  value       = { for k, s in aws_scheduler_schedule.job : k => s.schedule_expression }
}

output "failure_rule_name" {
  value = aws_cloudwatch_event_rule.ops_task_failed.name
}

output "scheduler_role_arn" {
  value = aws_iam_role.scheduler.arn
}
