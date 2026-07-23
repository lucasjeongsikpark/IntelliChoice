data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "frontend" {
  bucket = "${var.name_prefix}-${var.app_name}-web-${data.aws_caller_identity.current.account_id}"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_cloudfront_function" "spa_fallback" {
  name    = "${var.name_prefix}-${var.app_name}-spa-fallback"
  runtime = "cloudfront-js-2.0"
  comment = "Rewrite extensionless paths to /index.html for client-side routing (frontend behavior only)"
  publish = true
  code    = file("${path.module}/spa-fallback.js")
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.name_prefix}-${var.app_name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

locals {
  s3_origin_id  = "${var.app_name}-s3"
  alb_origin_id = "${var.app_name}-alb"

  # AWS managed policies (stable IDs, documented at
  # https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cache-policy.html
  # and .../origin-request-policy.html) - reused instead of hand-rolling equivalents.
  cache_policy_caching_optimized   = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  cache_policy_caching_disabled    = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
  origin_request_policy_all_viewer = "216adef6-5c7f-47e4-b989-5492eafa07d3"
}

resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = var.price_class
  comment             = "${var.name_prefix}-${var.app_name}"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = local.s3_origin_id
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # ALB has no ACM cert (no registered domain yet - D-084) - CloudFront reaches it over
  # plain HTTP within the AWS backbone; the viewer-facing side is still always HTTPS via
  # CloudFront's own default *.cloudfront.net certificate below.
  origin {
    domain_name = var.alb_dns_name
    origin_id   = local.alb_origin_id

    # Both apps' colliding root-level routes (both register a literal `/dev/token`,
    # outside any router prefix - see D-084) are otherwise indistinguishable to the one
    # shared ALB by path alone. This header lets ALB listener rules disambiguate which
    # app a request is actually for on exactly those colliding paths.
    custom_header {
      name  = "X-IntelliChoice-App"
      value = var.app_name
    }

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
      # Default (30s) is well under the Bedrock gateway's own worst-case latency
      # (call_timeout_s=20 x up to 3 attempts + backoff ~65s) - a real 504 was hit live
      # during S32/D-084 verification. 60s is the self-service maximum (CloudFront
      # requires an AWS Support quota increase to go higher, up to 180s) - closes most
      # but not all of the gap; see D-084 for the remaining known tail-latency caveat.
      origin_read_timeout      = 60
      origin_keepalive_timeout = 60
    }
  }

  default_cache_behavior {
    target_origin_id       = local.s3_origin_id
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = local.cache_policy_caching_optimized
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_fallback.arn
    }
  }

  dynamic "ordered_cache_behavior" {
    for_each = var.api_path_patterns
    content {
      path_pattern             = ordered_cache_behavior.value
      target_origin_id         = local.alb_origin_id
      viewer_protocol_policy   = "redirect-to-https"
      allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods           = ["GET", "HEAD"]
      cache_policy_id          = local.cache_policy_caching_disabled
      origin_request_policy_id = local.origin_request_policy_all_viewer
      compress                 = false
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = var.tags
}

data "aws_iam_policy_document" "frontend_bucket" {
  statement {
    sid       = "AllowCloudFrontOAC"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.this.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket.json
}
