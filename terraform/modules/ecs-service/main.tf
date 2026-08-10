resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name_prefix}-${var.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# D-244: where the collector's `awsemf` exporter writes Embedded Metric Format records.
#
# **A separate group from the application's, deliberately.** EMF records are a transport,
# not a diagnostic - CloudWatch extracts the metric from each one and the metric persists
# on its own retention. Mixing them into `/ecs/<service>` would bury `bedrock_call` and
# every Logs Insights query behind a wall of machine-written JSON, and the five existing
# metric filters read that group.
#
# One day of retention for the same reason: the *metrics* live in CloudWatch Metrics for
# fifteen months regardless. Keeping the raw EMF longer would pay storage twice for the
# same numbers.
resource "aws_cloudwatch_log_group" "metrics" {
  count             = var.enable_otel_sidecar ? 1 : 0
  name              = "/ecs/${var.name_prefix}-${var.name}/emf"
  retention_in_days = 1
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
    unhealthy_threshold = var.health_check_unhealthy_threshold
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

  container_definitions = jsonencode(concat([
    {
      name  = var.name
      image = var.image
      # AUD-F-28: opt-in explicit CPU share - see `pin_app_container_cpu`. Null (the
      # default) leaves the field unset, which is what every service has run with to date.
      cpu = var.pin_app_container_cpu ? (
        var.cpu - (var.enable_otel_sidecar ? var.otel_collector_cpu : 0)
      ) : null
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
    ],
    # S39: the OTLP collector the app's `OTEL_ENABLED=true` path exports to. See
    # variables.tf's `enable_otel_sidecar` for why this is a sidecar and not a service.
    var.enable_otel_sidecar ? [
      {
        name   = "otel-collector"
        image  = var.otel_collector_image
        cpu    = var.otel_collector_cpu
        memory = var.otel_collector_memory
        # Deliberately NOT essential: a collector that fails to start must not take a
        # healthy API down with it. Losing traces is a diagnostic gap; losing the service
        # is an outage, and this is being added *to* an environment the audits depend on.
        essential = false
        # The collector writes its own queue/checkpoint state, so it cannot run with the
        # read-only root filesystem D-088 gives the app containers.
        readonlyRootFilesystem = false
        environment = [
          # AWS's distro ships a built-in config that accepts OTLP and exports to X-Ray;
          # naming it here avoids mounting a config file into Fargate (which would need a
          # volume or a rebuilt image).
          { name = "AOT_CONFIG_CONTENT", value = local.otel_collector_config },
        ]
        logConfiguration = {
          logDriver = "awslogs"
          options = {
            "awslogs-group"         = aws_cloudwatch_log_group.this.name
            "awslogs-region"        = var.region
            "awslogs-stream-prefix" = "otel-collector"
          }
        }
      }
    ] : []
  ))

  tags = var.tags
}

locals {
  # OTLP in (what `packages/observability` speaks) → X-Ray out (queryable with the AWS CLI,
  # which is what the §2.6 criterion-9 PII scan needs). Batching keeps the export off the
  # request path.
  #
  # `awsxray` is used rather than an OTLP-to-CloudWatch path because X-Ray segments can be
  # fetched and walked as structured documents (`aws xray batch-get-traces`), and a PII scan
  # that cannot parse its own target is the mistake D-101 §5 records: a `CAST(blob AS text)
  # LIKE` check over msgpack certified a database full of coordinates as clean.
  #
  # D-244 adds a second pipeline: Prometheus in → CloudWatch EMF out. `packages/
  # observability/metrics.py` has defined twenty §5.32.4 KPIs since S17 and both apps have
  # served them at `/metrics` ever since - and **nothing in AWS has ever scraped them.**
  # Prometheus and Grafana exist only in `docker-compose.yml`, so every product signal
  # (sessions started, exams completed, learning gain, cost per session, citations per
  # answer, out-of-scope refusals) was computed in the running process and discarded.
  # CloudWatch held five metrics per service, all of them derived from log lines about
  # Bedrock.
  #
  # The sidecar is used rather than a scraper because it is already here: same container,
  # same task role, same lifecycle. `localhost` reaches the app because Fargate `awsvpc`
  # tasks share one network namespace, and `/metrics` is already exempt from the rate
  # limiter (`intellichoice_shared.rate_limit`), so a 60s scrape needs no new exception.
  otel_collector_config = yamlencode({
    receivers = {
      otlp = {
        protocols = {
          http = { endpoint = "0.0.0.0:4318" }
          grpc = { endpoint = "0.0.0.0:4317" }
        }
      }
      prometheus = {
        config = {
          scrape_configs = [{
            job_name = var.name
            # 60s, not the Prometheus default 15s: these are business counters read on a
            # dashboard, not an autoscaling signal, and the EMF record count is what the
            # ingestion bill is priced on.
            scrape_interval = "60s"
            metrics_path    = "/metrics"
            static_configs  = [{ targets = ["localhost:${var.container_port}"] }]
          }]
        }
      }
    }
    processors = {
      batch = { timeout = "5s", send_batch_size = 50 }
      # **The allowlist is a cost control, and it is strict on purpose.** `prometheus_client`
      # registers `python_gc_*`, `python_info` and a dozen `process_*` collectors into the
      # default registry, none of which say anything about this product; and every distinct
      # dimension combination CloudWatch sees is separately billed. Naming the twenty KPIs
      # explicitly means a metric added to `metrics.py` does not silently start costing
      # money - it has to be added here too, which is the right place to notice.
      "filter/kpis" = {
        metrics = {
          include = {
            match_type = "strict"
            metric_names = [
              "learning_session_starts_total",
              "learning_attendance_checks_total",
              "learning_exam_completions_total",
              "learning_sessions_completed_total",
              "learning_gain_score",
              "learning_support_usage_total",
              "learning_retry_total",
              "learning_checkpoint_repairs_total",
              "learning_tutor_review_flagged_total",
              "learning_problem_reports_total",
              "learning_quarantine_total",
              "learning_session_cost_cents",
              "qa_answers_total",
              "qa_citations_per_answer",
              "qa_email_escalations_total",
              "qa_maps_calls_total",
              "qa_calendar_calls_total",
              "qa_out_of_scope_total",
              "qa_service_degraded_total",
              "qa_conversation_cost_cents",
              "http_requests_total",
              "http_request_duration_seconds",
            ]
          }
        }
      }
    }
    exporters = {
      awsxray = { region = var.region }
      awsemf = {
        region         = var.region
        namespace      = "IntelliChoice/${var.name_prefix}/${var.name}"
        log_group_name = "/ecs/${var.name_prefix}-${var.name}/emf"
        # Without this the exporter also emits a zero-dimension rollup of every metric,
        # doubling the billed series to say something the dimensioned version already says.
        dimension_rollup_option = "NoDimensionRollup"
        # A metric not named here is still scraped and still written as an EMF field - it
        # simply is not promoted to a CloudWatch metric. So this list, not the filter above,
        # is what the bill is proportional to.
        #
        # **Dimensions are kept to at most one label.** `http_requests_total` carries
        # (app, method, path, status); indexing all four would create a metric per route
        # per status per method - hundreds of series to answer a question the ALB metrics
        # already answer. Indexed on `status` alone, it answers the one thing the ALB
        # cannot: which *application* status codes, distinguished from edge errors.
        metric_declarations = [
          {
            dimensions = [[]]
            metric_name_selectors = [
              "learning_session_starts_total",
              "learning_sessions_completed_total",
              "learning_gain_score",
              "learning_retry_total",
              "learning_checkpoint_repairs_total",
              "learning_tutor_review_flagged_total",
              "learning_problem_reports_total",
              "learning_quarantine_total",
              "learning_session_cost_cents",
              "qa_citations_per_answer",
              "qa_email_escalations_total",
              "qa_out_of_scope_total",
              "qa_conversation_cost_cents",
              "http_request_duration_seconds",
            ]
          },
          {
            dimensions = [["result"]]
            metric_name_selectors = ["learning_attendance_checks_total", "qa_answers_total",
            "qa_maps_calls_total", "qa_calendar_calls_total"]
          },
          {
            dimensions            = [["phase"]]
            metric_name_selectors = ["learning_exam_completions_total"]
          },
          {
            dimensions            = [["support_type"]]
            metric_name_selectors = ["learning_support_usage_total"]
          },
          {
            dimensions            = [["stage"]]
            metric_name_selectors = ["qa_service_degraded_total"]
          },
          {
            dimensions            = [["status"]]
            metric_name_selectors = ["http_requests_total"]
          },
        ]
      }
    }
    service = {
      pipelines = {
        traces = {
          receivers  = ["otlp"]
          processors = ["batch"]
          exporters  = ["awsxray"]
        }
        metrics = {
          receivers  = ["prometheus"]
          processors = ["filter/kpis", "batch"]
          exporters  = ["awsemf"]
        }
      }
    }
  })
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
# future work if CPU-based scaling proves too slow to react in practice). AUD-F-14
# measured that "too slow" was in fact "never" for chat-api: p95 sat at 31s while CPU
# peaked at 15%, so `enable_latency_step_scaling` below swaps this policy for
# latency-driven step scaling per service. Bounded to a
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
  count              = var.enable_autoscaling && !var.enable_latency_step_scaling ? 1 : 0
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

# AUD-F-14: latency-driven step scaling for I/O-bound services (see the variable's
# comment for why this replaces rather than augments the CPU policy). The scale-out
# alarm mirrors the observability module's notification alarm (`TargetResponseTime`
# p95 > 3s - see that module for the full S34 threshold rationale) but is a separate
# resource on purpose: the notification alarm's only action stays the SNS topic, so
# criterion 8's "alarm reaches a monitored inbox" evidence is unentangled with scaling,
# and scaling reacts after 2 breaching minutes rather than the notification's 3.
resource "aws_appautoscaling_policy" "latency_scale_out" {
  count              = var.enable_autoscaling && var.enable_latency_step_scaling ? 1 : 0
  name               = "${var.name_prefix}-${var.name}-p95-latency-scale-out"
  policy_type        = "StepScaling"
  service_namespace  = aws_appautoscaling_target.this[0].service_namespace
  resource_id        = aws_appautoscaling_target.this[0].resource_id
  scalable_dimension = aws_appautoscaling_target.this[0].scalable_dimension

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 120
    metric_aggregation_type = "Average"

    # Bounds are relative to the alarm threshold (3s): p95 3-10s adds one task,
    # anything past 10s (AUD-F-14's incident measured 31s) jumps by two, capped by
    # the target's max_capacity.
    step_adjustment {
      metric_interval_lower_bound = 0
      metric_interval_upper_bound = 7
      scaling_adjustment          = 1
    }
    step_adjustment {
      metric_interval_lower_bound = 7
      scaling_adjustment          = 2
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "latency_scale_out" {
  count               = var.enable_autoscaling && var.enable_latency_step_scaling ? 1 : 0
  alarm_name          = "${var.name_prefix}-${var.name}-p95-latency-scale-out"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p95"
  threshold           = 3
  treat_missing_data  = "notBreaching"
  alarm_description   = "AUD-F-14: ${var.name} p95 over 3s for 2 minutes - scale out (CPU cannot see this workload's saturation)."
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = aws_lb_target_group.this.arn_suffix
  }
  alarm_actions = [aws_appautoscaling_policy.latency_scale_out[0].arn]
  tags          = var.tags
}

# Scale-in leg: p95 comfortably under 1s for 15 consecutive minutes. `TargetResponseTime`
# publishes nothing when there are no requests at all, so missing data is treated as
# breaching - "no traffic" is the strongest possible evidence the extra tasks are idle.
# At min_capacity the policy's -1 is a no-op, so the alarm sitting in ALARM overnight is
# harmless.
#
# ⚠️ AUD-F-33 / D-182: the paragraph above was right about the evidence and wrong about the
# effect, and that was the defect the `FILL` expression below fixes. `treat_missing_data =
# "breaching"` alone made the alarm ENTER ALARM with 15 evaluated datapoints and no VALUE on
# any of them, and a step-scaling policy cannot select a step adjustment without a metric
# value - so Application Auto Scaling rejected the invocation ("Metric data points must be
# provided") and created no scaling activity at all, which is why `describe-scaling-activities`
# looked empty to D-132. Measured deterministic across 46 invocations on both services: 26
# refused all with no value, 20 accepted all with one. Net effect before the fix: SCALE-IN
# REQUIRED TRAFFIC, so a service that went fully idle after a scale-out stayed at elevated
# capacity - and the quieter service was the stuck one.
# Note the scale-out leg never had this shape: it uses `notBreaching`, so it cannot enter
# ALARM without data and never hands Auto Scaling an empty evaluation.
# Verify with `make scaling-evidence` - it exits 0 only when every ALARM transition carried a
# value Auto Scaling could act on.
resource "aws_appautoscaling_policy" "latency_scale_in" {
  count              = var.enable_autoscaling && var.enable_latency_step_scaling ? 1 : 0
  name               = "${var.name_prefix}-${var.name}-p95-latency-scale-in"
  policy_type        = "StepScaling"
  service_namespace  = aws_appautoscaling_target.this[0].service_namespace
  resource_id        = aws_appautoscaling_target.this[0].resource_id
  scalable_dimension = aws_appautoscaling_target.this[0].scalable_dimension

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 300
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = -1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "latency_scale_in" {
  count               = var.enable_autoscaling && var.enable_latency_step_scaling ? 1 : 0
  alarm_name          = "${var.name_prefix}-${var.name}-p95-latency-scale-in"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 15
  threshold           = 1
  alarm_description   = "AUD-F-14: ${var.name} p95 under 1s (or no traffic, filled as 0s) for 15 minutes - scale back in. AUD-F-33/D-182: the FILL is what makes this actionable."

  # AUD-F-33 / D-182. `FILL(m1, 0)` turns a minute with no requests into a p95 of 0 s, which
  # is both true and - the point - a metric VALUE. Auto Scaling needs one to select a step
  # adjustment, and an alarm that reached ALARM purely through `treat_missing_data` carries
  # none, so the invocation was refused 26 times out of 26.
  #
  # `FILL` is documented to have nothing to fill on an *entirely* absent series, so that was
  # checked before this was written rather than after: `get-metric-data` over
  # 2026-07-31T00:36Z-00:51Z, the window behind a real refusal, returns 15 values of 0.0 where
  # the raw metric returns none. No anchoring metric is needed.
  metric_query {
    id          = "e1"
    expression  = "FILL(m1, 0)"
    label       = "${var.name} p95 latency, idle minutes as 0s"
    return_data = true
  }

  metric_query {
    id          = "m1"
    return_data = false

    metric {
      namespace   = "AWS/ApplicationELB"
      metric_name = "TargetResponseTime"
      period      = 60
      stat        = "p95"
      dimensions = {
        LoadBalancer = var.alb_arn_suffix
        TargetGroup  = aws_lb_target_group.this.arn_suffix
      }
    }
  }

  # Kept at `breaching` deliberately, and it is now a fallback rather than the mechanism. With
  # the FILL supplying a value every minute this should never apply; if the expression ever
  # stops returning data, `breaching` reproduces the OLD behaviour - an ALARM the policy
  # refuses - which `make scaling-evidence` detects. `missing` would instead fail silently, and
  # a silent version of this defect is what cost four days.
  treat_missing_data = "breaching"

  alarm_actions = [aws_appautoscaling_policy.latency_scale_in[0].arn]
  tags          = var.tags
}
