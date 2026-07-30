# CloudTrail — SPEC §5.30.3, closing traceability finding T-01 (D-124/D-125).
#
# This was in the spec from the start and had simply never been built or decided against;
# a grep for it across docs/ found one incidental mention and no decision. It is enabled
# rather than deferred because it is close to free at this scale and because the project's
# own INCIDENT_RESPONSE.md is grounded in two real credential incidents (S32/D-084,
# S33/D-085) and had no account-level audit log to point at. "Who used that key, and when"
# is the first question of any credential incident, and until now nothing could answer it.
#
# Cost shape, since that is what deferred WAF and GuardDuty: the FIRST copy of management
# events in an account is free, forever, with a 90-day console history. What costs money is
# a second trail, data events (S3 object-level, Lambda invoke), and S3 storage for the
# delivered logs. So this trail takes management events only, and the bucket expires
# objects on a schedule - a trail nobody prunes is how a free feature turns into a bill.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

# The log bucket. Deliberately separate from any application bucket: CloudTrail's own
# bucket policy grants the service write access, and that is not a grant to co-locate with
# anything else.
resource "aws_s3_bucket" "trail" {
  bucket = "${var.name_prefix}-cloudtrail-${data.aws_caller_identity.current.account_id}"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "trail" {
  bucket                  = aws_s3_bucket.trail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "trail" {
  bucket = aws_s3_bucket.trail.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Versioning so a delete cannot silently erase history; the lifecycle rule below still
# bounds what is retained, including the noncurrent versions this creates.
resource "aws_s3_bucket_versioning" "trail" {
  bucket = aws_s3_bucket.trail.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "trail" {
  bucket = aws_s3_bucket.trail.id

  # Explicit dependency: S3 rejects a lifecycle configuration that references noncurrent
  # versions on a bucket where versioning is not yet enabled, and Terraform has no implicit
  # edge between these two resources.
  depends_on = [aws_s3_bucket_versioning.trail]

  rule {
    id     = "expire-trail-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.log_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.log_retention_days
    }

    # Without this, a failed multipart upload bills storage forever with nothing listing it.
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# CloudTrail's write grant. Both statements carry an `aws:SourceArn` condition naming this
# exact trail: without it the policy authorizes *any* account's trail to deliver here (the
# confused-deputy shape AWS's own docs call out), and a bucket that accepts foreign log
# delivery is worse than no audit log, because the contents can no longer be trusted.
data "aws_iam_policy_document" "trail_bucket" {
  statement {
    sid    = "AWSCloudTrailAclCheck"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.trail.arn]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = [local.trail_arn]
    }
  }

  statement {
    sid    = "AWSCloudTrailWrite"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.trail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = [local.trail_arn]
    }
  }
}

locals {
  # Computed rather than referencing aws_cloudtrail.this.arn, which would be a cycle: the
  # trail depends on the bucket policy, and the policy needs the trail's ARN.
  trail_arn = "arn:${data.aws_partition.current.partition}:cloudtrail:${var.aws_region}:${data.aws_caller_identity.current.account_id}:trail/${var.name_prefix}-trail"
}

resource "aws_s3_bucket_policy" "trail" {
  bucket = aws_s3_bucket.trail.id
  policy = data.aws_iam_policy_document.trail_bucket.json
}

resource "aws_cloudtrail" "this" {
  name           = "${var.name_prefix}-trail"
  s3_bucket_name = aws_s3_bucket.trail.id

  # Multi-region even though everything runs in one: the point of an audit log is to record
  # activity you did not expect, and unexpected activity in an unused region is exactly the
  # case a single-region trail cannot see. Management events are free in every region.
  is_multi_region_trail = true

  # Global service events (IAM, STS, CloudFront) are region-less and only land in a trail
  # that asks for them - and IAM/STS is precisely what a credential incident needs to read.
  include_global_service_events = true

  # Digest files, so tampering with delivered logs is detectable rather than assumed-away.
  enable_log_file_validation = true

  # No `event_selector` block: management events only. Data events (S3 object-level, Lambda
  # invoke) are the paid tier and are what turn a free trail into a surprising bill. If they
  # are ever wanted, add them deliberately and price them first.

  tags = var.tags

  # The bucket policy must exist before the trail, or CloudTrail's create-time delivery
  # check fails with an unhelpful "incorrect bucket policy" error.
  depends_on = [aws_s3_bucket_policy.trail]
}
