resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name_prefix}-${var.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lb_target_group" "this" {
  # Target group names share ALB's 32-char AWS limit - var.name_prefix alone
  # ("intellichoice-staging") already leaves no room for it plus var.name, so this
  # deliberately skips the env prefix (this account only has one environment's worth of
  # target groups today; add one back if a second environment ever coexists here).
  name        = "${var.name}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
    matcher             = "200"
  }

  tags = var.tags
}

resource "aws_lb_listener_rule" "this" {
  listener_arn = var.listener_arn
  priority     = var.listener_rule_priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }

  condition {
    path_pattern {
      values = var.path_patterns
    }
  }
}

resource "aws_ecs_task_definition" "this" {
  family                   = "${var.name_prefix}-${var.name}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  # ARM64/Graviton, not Fargate's x86_64 default - matches images built locally on
  # Apple Silicon (no cross-compilation step needed) and is ~20% cheaper per vCPU/GB
  # than x86_64 Fargate (D-084's cost posture). Must match whatever architecture the
  # pushed image was actually built for, or tasks fail at startup (exec format error).
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name                   = var.name
      image                  = var.image
      essential              = true
      readonlyRootFilesystem = var.read_only_root_filesystem
      portMappings = [
        { containerPort = var.container_port, protocol = "tcp" }
      ]
      environment = [for k, v in var.environment : { name = k, value = v }]
      secrets     = [for k, arn in var.secrets : { name = k, valueFrom = arn }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = var.name
        }
      }
    }
  ])

  tags = var.tags
}

resource "aws_ecs_service" "this" {
  name            = "${var.name_prefix}-${var.name}"
  cluster         = var.cluster_id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  enable_execute_command = var.enable_execute_command

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = var.name
    container_port   = var.container_port
  }

  # Give the container time to establish DB connections in `lifespan` (both apps connect
  # eagerly on startup, not lazily) before the ALB starts routing to it. 30s was too
  # tight in practice - a real learning-api rollout during S32/D-084 failed its first
  # attempt (target group deregistered it before accumulating the 2 checks x 15s
  # interval the target group's own healthy_threshold needs, on top of Fargate ENI
  # attach + task startup time); ECS's automatic retry succeeded on attempt 2, but 60s
  # removes the margin call entirely rather than relying on the retry.
  health_check_grace_period_seconds = 60

  # S34/SPEC §6.23 "rolling deployment" + Phase 23's rollback-trigger intent, the ECS-
  # native equivalent: if a newly-deployed task definition revision never reaches a
  # steady healthy state (e.g. it crash-loops or keeps failing target-group health
  # checks), ECS automatically rolls the service back to the last known-good revision
  # itself, without waiting for deploy-staging.yml's own post-deploy checks. This is a
  # deploy-time safety net (bad task definition never becomes healthy at all); the
  # canary bake + CloudWatch-alarm rollback in deploy-staging.yml is a complementary,
  # separate safety net for the case a new revision *is* healthy but is quietly serving
  # bad responses (elevated 5xx/latency) - circuit breaker alone can't catch that.
  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener_rule.this]

  # deploy-staging.yml deploys by registering a new task definition revision and calling
  # `aws ecs update-service` directly (CI never runs `terraform apply` unattended - S32/
  # D-084's deliberate choice, keeping infra-creation blast radius out of CI). Without
  # this, the next human-run `terraform apply` would see the service pointed at a
  # revision it didn't create and silently roll it back to whatever image tag is in
  # tfvars. Terraform still owns the task definition's *shape* (cpu/memory/env/secrets) -
  # a real shape change needs a manual apply that also updates the running service
  # (this ignore only affects which revision the service points at, not template changes
  # to aws_ecs_task_definition.this itself). `desired_count` is ignored too, once
  # `var.enable_autoscaling` is true (S34) - Application Auto Scaling manages the live
  # count directly via the ECS API, outside Terraform's knowledge; without this, the next
  # `terraform apply` would silently scale a busy service back down to `var.desired_count`.
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  tags = var.tags
}

locals {
  # `var.cluster_id` is the cluster ARN (`aws_ecs_cluster.this.id` in the root module) -
  # Application Auto Scaling's resource_id needs the plain cluster *name*, the second
  # "/"-delimited segment of an ECS cluster ARN. Avoids needing a second, redundant
  # "cluster name" input variable alongside `cluster_id`.
  cluster_name = element(split("/", var.cluster_id), 1)
}

# S34/SPEC §5.33.4 "HPA signals" (CPU/memory/active-requests/SSE-connections/P95
# latency), translated to ECS's real equivalent - Fargate has no HPA, and until this
# session nothing here auto-scaled at all (`desired_count` was a flat, fixed number).
# CPU-utilization target-tracking is the simplest of SPEC's listed signals to wire up
# with no extra infrastructure (ALB request-count-per-target scaling would react faster
# to the I/O-bound concurrency this app's own S34 load test actually bottlenecked on,
# but needs the target group's ARN suffix wired through as a second signal - left as
# future work if CPU-based scaling proves too slow to react in practice). Bounded to a
# modest `max_capacity` (default 3) deliberately, not "as high as possible" - this
# account is still on Free Tier constraints (D-084) and a solo-maintainer ~1,000-MAU
# target doesn't need enterprise-scale headroom.
resource "aws_appautoscaling_target" "this" {
  count              = var.enable_autoscaling ? 1 : 0
  service_namespace  = "ecs"
  resource_id        = "service/${local.cluster_name}/${aws_ecs_service.this.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = var.autoscaling_min_capacity
  max_capacity       = var.autoscaling_max_capacity
}

resource "aws_appautoscaling_policy" "cpu" {
  count              = var.enable_autoscaling ? 1 : 0
  name               = "${var.name_prefix}-${var.name}-cpu-target-tracking"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.this[0].service_namespace
  resource_id        = aws_appautoscaling_target.this[0].resource_id
  scalable_dimension = aws_appautoscaling_target.this[0].scalable_dimension

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.autoscaling_cpu_target_percent
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}
