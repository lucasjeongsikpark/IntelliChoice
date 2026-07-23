# One shared task definition for every one-off in-VPC operation this deployment needs
# (Alembic migrations, MySQL schema/seed, ad-hoc verification queries) - launched on
# demand via `aws ecs run-task` with a `containerOverrides` command, never a standing
# service. Reuses the learning-api image since it already has every workspace package
# (packages/db's Alembic config, packages/adapters' seed scripts) installed.
resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name_prefix}-ops-task"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_ecs_task_definition" "this" {
  family                   = "${var.name_prefix}-ops-task"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  # Matches ecs-service's ARM64/Graviton choice (D-084) - this task runs the same
  # (ARM64-built) learning-api image.
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "ops-task"
      image     = var.image
      essential = true
      # No real ENTRYPOINT/CMD is meant to run standalone - every invocation supplies
      # `containerOverrides.command` at `run-task` time (e.g. ["alembic", "upgrade",
      # "head"]). This default just keeps the task definition valid/registerable.
      command     = ["true"]
      environment = [for k, v in var.environment : { name = k, value = v }]
      secrets     = [for k, arn in var.secrets : { name = k, valueFrom = arn }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ops-task"
        }
      }
    }
  ])

  tags = var.tags
}
