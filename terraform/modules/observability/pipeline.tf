# D-244: the offline question-generation pipeline, made visible.
#
# **What was true before this file.** `packages/curriculum` imported nothing from
# `intellichoice_observability`, defined no logger, and reported through 22 `print()`
# calls. The ops task runs it in ECS, so that output was already reaching CloudWatch - as
# unstructured text, which is the difference between a log and a record. Nothing could be
# queried, counted or alarmed on.
#
# It is also the component that spends money in bulk. D-238, D-240 and D-243 each had to
# reconstruct what a paid batch did *afterwards*, from `question_validation_runs`, because
# the run itself left nothing readable behind. The gateway had been computing per-call
# cost, duration and failure reason the whole time; with no logging handler configured they
# were formatted and dropped.
#
# These filters read the records `pipeline_cli` and `loader` now emit. Deliberately on the
# ops-task log group and not the services': the same `bedrock_call` event name appears in
# both, and folding them together would mean an offline batch's spend and a student's
# session cost showed up as one number.

# Every candidate the pipeline resolves, by outcome. The one number that says whether a
# run was worth its money - D-243 moved it from 27% to 55% and had to buy a second batch
# to find that out, because the first batch's result existed only as terminal scrollback.
resource "aws_cloudwatch_log_metric_filter" "pipeline_candidates" {
  for_each = {
    filled   = "{ $.event = \"pipeline_run_complete\" && $.filled = * }"
    rejected = "{ $.event = \"pipeline_run_complete\" && $.rejected = * }"
    cost     = "{ $.event = \"pipeline_run_complete\" && $.total_cost_cents = * }"
  }
  name           = "${var.name_prefix}-pipeline-${each.key}"
  log_group_name = var.ops_task_log_group
  pattern        = each.value

  metric_transformation {
    name      = "Pipeline${title(each.key)}"
    namespace = local.pipeline_namespace
    value     = "$.${each.key == "cost" ? "total_cost_cents" : each.key}"
    unit      = "None"
    # A run that produced nothing is a real zero and must plot as one. Without this a
    # failed batch and a batch that never ran are the same empty chart - which is exactly
    # the confusion D-242 spent a session on, one system over.
    default_value = 0
  }
}

# The loader's summary, which D-206 and D-235 both needed and neither could get.
#
# Carry-over #11, closed: `deploy-staging.yml` asserts `test "$EXIT_CODE" = "0"` and
# nothing else, so "the deploy loaded the bank" has only ever meant "the loader exited 0".
# D-235's defect - an edit to an existing item silently discarded - hid behind the line
# "127 already existed, 0 created" for twelve decisions, and that line was not in any
# queryable form. `TemplatesCreated`/`Updated`/`Retired` are now three separate numbers a
# deploy can be checked against.
resource "aws_cloudwatch_log_metric_filter" "curriculum_load" {
  for_each = toset(["templates_created", "templates_updated", "templates_retired"])
  name     = "${var.name_prefix}-curriculum-${each.key}"
  # D-244: ``$.field = *`` rather than a bare event match, same reasoning as the Bedrock
  # filters - a renamed field becomes a flat line rather than a run of zeros that reads as
  # a healthy quiet period.
  log_group_name = var.ops_task_log_group
  pattern        = "{ $.event = \"curriculum_load_complete\" && $.${each.key} = * }"

  metric_transformation {
    name          = "Curriculum${join("", [for part in split("_", each.key) : title(part)])}"
    namespace     = local.pipeline_namespace
    value         = "$.${each.key}"
    unit          = "None"
    default_value = 0
  }
}

# A pipeline run that ends on its budget rather than on its plan. Not a failure - the cap
# did its job - but a truncated batch compared against a complete one is how a yield number
# quietly stops meaning anything, which is the D-192 confusion `RunSummary` was split up to
# prevent. Worth seeing rather than worth paging on, so it has no alarm.
resource "aws_cloudwatch_log_metric_filter" "pipeline_stopped_early" {
  name           = "${var.name_prefix}-pipeline-stopped-early"
  log_group_name = var.ops_task_log_group
  pattern        = "{ $.event = \"pipeline_run_complete\" && $.stopped_early = \"run_budget_reached\" }"

  metric_transformation {
    name          = "PipelineStoppedEarly"
    namespace     = local.pipeline_namespace
    value         = "1"
    unit          = "Count"
    default_value = 0
  }
}
