# Restrict direct access to CloudFront's own origin-facing IP ranges, not 0.0.0.0/0 -
# the intended entry point is CloudFront (D-084's same-origin frontend+API design), and
# this keeps the ALB from being reachable by anyone who skips it, even before a WAF exists.
data "aws_ec2_managed_prefix_list" "cloudfront_origin_facing" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb-sg"
  description = "Allow HTTP from CloudFronts origin-facing ranges only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "HTTP from CloudFront"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront_origin_facing.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-alb-sg" })
}

resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  # Default (60s) is close to the Bedrock gateway's own worst-case latency
  # (call_timeout_s=20 x up to 3 attempts + backoff ~65s) - a real 504 was hit live
  # during S32/D-084 verification. 120s gives real headroom without masking a
  # genuinely stuck backend forever.
  idle_timeout = 120

  tags = var.tags
}

# No ACM cert exists yet (no registered domain - D-084) - HTTP-only listener; CloudFront
# terminates real viewer-facing TLS in front of this origin. Default action 404s so an
# unmatched path (or anyone hitting the ALB DNS name directly) doesn't accidentally reach
# either app's catch-all route.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Not found"
      status_code  = "404"
    }
  }
}
