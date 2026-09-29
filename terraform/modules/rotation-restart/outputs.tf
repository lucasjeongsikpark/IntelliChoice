output "rule_name" {
  value = aws_cloudwatch_event_rule.rotation_succeeded.name
}

output "function_name" {
  description = "For the post-apply check: rotate a secret on demand and watch this function's log group."
  value       = aws_lambda_function.this.function_name
}

output "alarm_name" {
  value = aws_cloudwatch_metric_alarm.errors.alarm_name
}
