output "trail_arn" {
  description = "ARN of the CloudTrail trail."
  value       = aws_cloudtrail.this.arn
}

output "trail_name" {
  description = "Name of the trail — what `aws cloudtrail get-trail-status --name` takes."
  value       = aws_cloudtrail.this.name
}

output "log_bucket_name" {
  description = "S3 bucket receiving the delivered logs."
  value       = aws_s3_bucket.trail.id
}
