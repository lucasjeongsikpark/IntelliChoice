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
      name      = var.name
      image     = var.image
      essential = true
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

  depends_on = [aws_lb_listener_rule.this]

  # deploy-staging.yml deploys by registering a new task definition revision and calling
  # `aws ecs update-service` directly (CI never runs `terraform apply` unattended - S32/
  # D-084's deliberate choice, keeping infra-creation blast radius out of CI). Without
  # this, the next human-run `terraform apply` would see the service pointed at a
  # revision it didn't create and silently roll it back to whatever image tag is in
  # tfvars. Terraform still owns the task definition's *shape* (cpu/memory/env/secrets) -
  # a real shape change needs a manual apply that also updates the running service
  # (this ignore only affects which revision the service points at, not template changes
  # to aws_ecs_task_definition.this itself).
  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = var.tags
}
