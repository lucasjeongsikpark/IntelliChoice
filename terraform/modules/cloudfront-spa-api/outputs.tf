output "distribution_id" {
  value = aws_cloudfront_distribution.this.id
}

output "distribution_domain_name" {
  value = aws_cloudfront_distribution.this.domain_name
}

output "distribution_arn" {
  value = aws_cloudfront_distribution.this.arn
}

output "bucket_name" {
  value = aws_s3_bucket.frontend.id
}

output "bucket_arn" {
  value = aws_s3_bucket.frontend.arn
}
