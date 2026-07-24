output "budget_name" {
  value = aws_budgets_budget.monthly.name
}

output "alarm_names" {
  description = "S34: every 5xx-rate/P95-latency alarm name, for deploy-staging.yml's post-deploy canary bake to poll."
  value = concat(
    [for a in aws_cloudwatch_metric_alarm.target_5xx : a.alarm_name],
    [for a in aws_cloudwatch_metric_alarm.target_latency_p95 : a.alarm_name],
  )
}

output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
