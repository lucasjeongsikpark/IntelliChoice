# D-377: the application layer, alarmed.
#
# **The shape of the gap the 2026-08-16 audit found.** The infrastructure layer here is
# thoroughly alarmed - 26 alarms across ALB, RDS, ECS, Bedrock and LangSmith. The application
# layer is thoroughly *logged* and almost entirely unalarmed: every P1 in that audit was a
# well-written, well-named log line that no metric filter read. The system is very good at
# telling you a machine is unhealthy and very poor at telling you a feature is quietly broken
# while every machine looks fine.
#
# `alarms.tf` already opens with this criticism, made about an earlier set of metrics: *"The
# five log-derived metrics in dashboard.tf were built to see exactly that class, and then
# nothing was ever set to fire on them - so the dashboard could show it, if a human happened
# to look."* This file is that sentence applied to the events the applications emit.
#
# Nothing here requires new instrumentation. Every event below is already produced, already
# structured, and already correctly named.

# --- Browser crashes ------------------------------------------------------------------
#
# The sink was built for learning in D-328 and for chat in D-372, and its module docstring
# states the purpose: *"A student's blank screen currently reaches no one, which is the one
# failure mode a parent notices and the server cannot see."*
#
# **The reporting half shipped and the noticing half did not.** The browser already sends a
# redacted stack and a `client_trace_id` that joins to the server span; nothing graphed it and
# nothing paged, so a frontend deploy that white-screens one browser family would sit until a
# human complained. Highest value per line in the audit - both ends already existed.
resource "aws_cloudwatch_log_metric_filter" "client_errors" {
  for_each       = var.log_group_names
  name           = "${var.name_prefix}-${each.key}-client-errors"
  log_group_name = each.value
  pattern        = "{ $.event = \"client_error\" }"

  metric_transformation {
    name      = "ClientErrors"
    namespace = local.metric_namespace[each.key]
    value     = "1"
    unit      = "None"
    # A quiet hour is a real zero here, unlike the `$.field = *` filters: absence of crashes
    # is the healthy state and must plot as one rather than as a gap.
    default_value = 0
  }
}

resource "aws_cloudwatch_metric_alarm" "client_errors" {
  for_each            = var.log_group_names
  alarm_name          = "${var.name_prefix}-${each.key}-client-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ClientErrors"
  namespace           = local.metric_namespace[each.key]
  period              = 900
  statistic           = "Sum"
  # Deliberately low. A render crash is not a rate to be tuned - one student staring at a
  # blank screen is the event, and `ErrorBoundary` fires once per failed render so a genuine
  # crash loop is bounded by the endpoint's own per-caller limit rather than by this.
  threshold          = var.client_error_alarm_threshold
  treat_missing_data = "notBreaching"
  alarm_description = join(" ", [
    "D-377: ${each.key}'s browser reported a crash. The payload carries a redacted stack and",
    "a `client_trace_id` that joins to the server-side span - search the log group for",
    "`client_error` at this timestamp. Until this alarm existed the report reached CloudWatch",
    "and nobody was told, which is the failure mode the sink was built to end.",
  ])
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}

# --- Silent background failures ---------------------------------------------------------
#
# **D-329/D-330's incident is fixed; the gap that let it run for 48 hours is not.** A
# background hint personalizer raised 117 times in two days - the only ERROR the service
# emitted - and nobody knew, because a detached task swallows exceptions by design and a
# failed personalization is *deliberately* indistinguishable from the canonical hint.
#
# `grep -rin "background_" terraform/` returned **zero** before this. Three detached
# schedulers end in `logger.exception("background_*_failed")` and nothing read any of them.
# The wildcard covers all three and anything added later that follows the convention, which
# is the point: the naming already existed and only the consumer was missing.
resource "aws_cloudwatch_log_metric_filter" "background_failures" {
  for_each       = var.log_group_names
  name           = "${var.name_prefix}-${each.key}-background-failures"
  log_group_name = each.value
  pattern        = "{ $.event = \"background_*_failed\" }"

  metric_transformation {
    name          = "BackgroundTaskFailures"
    namespace     = local.metric_namespace[each.key]
    value         = "1"
    unit          = "None"
    default_value = 0
  }
}

resource "aws_cloudwatch_metric_alarm" "background_failures" {
  for_each            = var.log_group_names
  alarm_name          = "${var.name_prefix}-${each.key}-background-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BackgroundTaskFailures"
  namespace           = local.metric_namespace[each.key]
  period              = 3600
  statistic           = "Sum"
  # Above zero, because these paths are supposed to be quiet - but not at 1, because a single
  # transient Bedrock failure is absorbed by design and the student still gets reviewed
  # content. D-329's rate was ~2.4/hour sustained, which this catches within the hour.
  threshold          = var.background_failure_alarm_threshold
  treat_missing_data = "notBreaching"
  alarm_description = join(" ", [
    "D-377: ${each.key} background tasks are failing. These degrade silently on purpose - the",
    "student keeps canonical content - so nothing else will tell you. D-329 ran 117 failures",
    "over 48 hours undetected. Search the log group for `background_` at this timestamp.",
  ])
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}

# --- The product KPI that means "students are getting through" --------------------------
#
# D-244 bridged 22 product KPIs into CloudWatch and **set zero alarms on any of them**, which
# is the same criticism one layer up. Two are added here rather than twenty-two, chosen
# because they answer the 2am question directly: is anyone completing anything?
#
# A low-watermark alarm is the right instrument and an awkward one, because zero is normal at
# 3am for a K-12 product. `evaluation_periods` over a long `period` is what separates "quiet
# night" from "broken since the 6pm deploy", and the threshold is a floor rather than a
# target - it fires when the number is *implausibly* low for a whole day, not when it dips.
resource "aws_cloudwatch_metric_alarm" "sessions_completed_floor" {
  count               = var.daily_completed_sessions_floor > 0 ? 1 : 0
  alarm_name          = "${var.name_prefix}-learning-sessions-completed-floor"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "learning_sessions_completed_total"
  namespace           = local.metric_namespace["learning-api"]
  period              = 86400
  statistic           = "Sum"
  threshold           = var.daily_completed_sessions_floor
  # **The inverse posture of every other alarm in this module, and it is deliberate.**
  # Elsewhere missing data means "nothing happened, which is fine". Here the absence of the
  # metric *is* the incident: a graph erroring on every turn emits no completions at all, and
  # `notBreaching` would render that as healthy.
  treat_missing_data = "breaching"
  alarm_description = join(" ", [
    "D-377: fewer than ${var.daily_completed_sessions_floor} learning sessions completed in",
    "24h. The cleanest single signal that the product is working end to end - a graph failing",
    "after the 6pm deploy looks exactly like this and nothing else would say so, because a",
    "session that never completes still returns 200s the whole way.",
  ])
  # D-401: informational. A KPI floor going unmet is a product signal, not a fault - and on
  # staging, where the only traffic is a test suite, an unmet floor is the normal overnight
  # state. On the page channel it is pure noise.
  alarm_actions = [aws_sns_topic.alerts_info.arn]
  ok_actions    = [aws_sns_topic.alerts_info.arn]
  tags          = var.tags
}

# --- Nightly maintenance: did it run, and did it do anything? ---------------------------
#
# **Two different questions, and before D-377 only the first was answerable.** The four
# enabled schedules report in unstructured `print()`, so a three-day structured-event query
# over the ops-task log group returned only the deploy-time loader. Read live from staging on
# 2026-08-16, today's consolidation run: *0 facts added, 3,181 events dropped over the call
# cap, 14.11 cents spent* - a job succeeding at doing nothing, visible only as prose.
#
# The CLIs now emit a `*_job_complete` record (see the Python side of D-377). These filters
# read it, and the alarm below is the half that matters most.
#
# **`replace(each.key, "-", "_")`, and the two spellings are not interchangeable (RD-01).** The
# emitter's event name is underscored (`report_job_complete` rewrites the hyphens) while the
# `job` field - the dimension below - stays the hyphenated key verbatim. Built from `each.key`
# directly, this pattern searched for `session-consolidate_job_complete`, an event nothing has
# ever written: `JobCompletions` published no datapoint on any of the four dimensions for
# fourteen days and all four heartbeat alarms sat in a permanent false ALARM from 2026-08-16.
#
# **Either side could have been the one line.** The event name and the `job` field are
# independent - the emitter could have written the hyphenated name verbatim and left the
# dimension untouched - so this is not the only correct fix. It is on this side for two
# reasons. **Deploy cost:** a terraform change reaches staging with an `apply`, while an
# emitter change is inert until a full image build and deploy (LB-05), which is gated on UD-1.
# **Convention:** underscored event names are what every structured event in this repository
# uses (`curriculum_load_complete`, `client_error`), so the terraform spelling was the odd one
# out. `test_scheduled_job_event_parity.py` now fails if either side moves alone.
resource "aws_cloudwatch_log_metric_filter" "nightly_jobs" {
  for_each       = toset(var.nightly_job_events)
  name           = "${var.name_prefix}-job-${each.key}"
  log_group_name = var.ops_task_log_group
  pattern        = "{ $.event = \"${replace(each.key, "-", "_")}_job_complete\" }"

  metric_transformation {
    name      = "JobCompletions"
    namespace = local.pipeline_namespace
    value     = "1"
    unit      = "None"
    # **No `default_value`, and CloudWatch enforces that** — it rejects `dimensions` and
    # `default_value` together (`InvalidParameterException: ... mutually exclusive`). That
    # constraint happens to give the right shape here rather than a compromise: with a
    # dimension, a job that never ran emits **no series at all**, and "no datapoint" is
    # exactly the condition the heartbeat below treats as breaching. A default of 0 would
    # manufacture a healthy-looking zero for a job that was never invoked, which is the
    # failure this whole pair exists to catch.
    dimensions = { job = "$.job" }
  }
}

# **The dead-man's switch, which is the finding rather than a nicety.**
#
# The existing alarm in `scheduled-jobs/main.tf` watches ECS task **exit != 0** - a job that
# runs and fails. A job that *never runs* emits no task-state event at all, so no rule
# matches and no alarm fires: a disabled schedule, a revoked `iam:PassRole`, a Scheduler-side
# failure and a `RunTask` that never launches are all indistinguishable from a quiet night.
# `grep` for `AWS/Scheduler` alarms in `terraform/` returned zero.
#
# For a 90-day retention promise over minors' chat data, **the absence of a failure is not
# evidence of a run**, and silence is the dangerous direction. Hence
# `treat_missing_data = "breaching"`: here missing data *is* the incident.
resource "aws_cloudwatch_metric_alarm" "nightly_job_heartbeat" {
  for_each            = toset(var.nightly_job_events)
  alarm_name          = "${var.name_prefix}-job-${each.key}-heartbeat"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "JobCompletions"
  namespace           = local.pipeline_namespace
  period              = 172800 # two days, so one missed night is a blip and two is an alarm
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "breaching"
  dimensions          = { job = each.key }
  alarm_description = join(" ", [
    "D-377: the ${each.key} nightly job has not reported a completion in 48h. The exit-code",
    "alarm cannot see this - a job that never starts emits no task-state event, so no failure",
    "is recorded and the silence reads as health. Check `aws scheduler get-schedule` and the",
    "ops-task log group before assuming it ran.",
  ])
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = var.tags
}
