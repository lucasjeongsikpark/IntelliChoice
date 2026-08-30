# COLLECTOR-STATS-UNSCRAPED / AUD-F-12: the telemetry pipeline, watched by something other
# than a person running a measurement.
#
# **The gap, stated as E6.2 left it:** *"The collector is `essential: false` by design (a
# collector that fails must not take the API down), and no alarm watches export failures. This
# run found no failure in either window and proved its reader, but the detection gap that let
# 100% span loss go unnoticed is a posture, not an incident, and it has not changed."*
#
# Two things had to be true for an alarm to exist here and only one of them was. The counters
# were always computed - the collector serves them on `localhost:8888` - and **nothing scraped
# them**, so there was no metric to alarm on. `modules/ecs-service/main.tf` now scrapes that
# endpoint and promotes exactly four counters; these alarms are the consumer, and without them
# the scrape would repeat the criticism `app_events.tf` opens with: a signal built to see a
# failure class, with nothing set to fire on it.
#
# **Why the quiet channel.** `langsmith_ingest_failed`'s precedent, and the same sentence
# applies verbatim: the observability leg is dark while this is firing, and app traffic is
# unaffected. A student mid-exam notices nothing when a span fails to reach X-Ray. Routing it
# to the page channel would put a diagnostic outage beside real ones at 2am, which is the exact
# unreadability D-401 split the topics to end. `test_alarm_severity_routing.py`'s closed list
# records this decision rather than leaving it implicit.
#
# **Why two exporters and not one alarm.** They fail for unrelated reasons and cost unrelated
# things. `awsxray` failing means traces stop - the diagnostic gap AUD-F-12 is named for.
# `awsemf` failing means every product KPI stops arriving while the dashboards keep rendering
# their last value - and the KPI floor alarm in `app_events.tf` is `treat_missing_data =
# "breaching"`, so an EMF outage would present as a *product* incident and send someone
# looking at the graph layer. One alarm per leg is what makes those distinguishable.
locals {
  # `{ "learning-api|awsxray" = {...} }` - flattened because terraform's `for_each` takes one
  # level, and the alarm needs both halves in its dimensions.
  collector_export_failure_alarms = {
    for pair in setproduct(tolist(var.otel_collector_services), [
      {
        exporter = "awsxray"
        metric   = "otelcol_exporter_send_failed_spans"
        subject  = "traces are not reaching X-Ray"
        cost     = "every trace for this window is gone - there is no retry after this counter moves, and X-Ray has no backfill"
      },
      {
        exporter = "awsemf"
        metric   = "otelcol_exporter_send_failed_metric_points"
        subject  = "product KPIs are not reaching CloudWatch"
        cost     = "the twenty-two SPEC 5.32.4 KPIs stop arriving; dashboards keep rendering and simply stop advancing, which reads as 'nobody used the product' rather than as a fault"
      },
      ]) : "${pair[0]}|${pair[1].exporter}" => {
      service  = pair[0]
      exporter = pair[1].exporter
      metric   = pair[1].metric
      subject  = pair[1].subject
      cost     = pair[1].cost
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "collector_export_failures" {
  for_each            = local.collector_export_failure_alarms
  alarm_name          = "${var.name_prefix}-${each.value.service}-collector-${each.value.exporter}-export-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = each.value.metric
  namespace           = local.app_metric_namespace[each.value.service]
  period              = 900
  statistic           = "Sum"
  threshold           = var.collector_export_failure_alarm_threshold
  # **`notBreaching`, and this is the one place in this file where that needs defending.**
  # The counters are exported through `awsemf`, which is one of the two things being watched -
  # so if `awsemf` dies entirely, this alarm's own metric stops arriving and it goes quiet
  # rather than firing. That is a real limit and it is not closable from here: an alarm cannot
  # be delivered by the pipeline it is monitoring.
  #
  # `breaching` would not fix it either - it would make both alarms fire permanently whenever
  # the services are idle enough that no span or metric point is exported, which on staging is
  # most of the night. The condition "the collector stopped entirely" has a different and
  # correct instrument: `otelcol_exporter_sent_spans` going flat, which is now a graphable
  # metric for the first time, and the ECS task-level alarms that see a container exit.
  treat_missing_data = "notBreaching"
  dimensions         = { exporter = each.value.exporter }
  alarm_description = join(" ", [
    "AUD-F-12/E6.2: ${each.value.service}'s OTel collector failed to export -",
    "${each.value.subject}. Consequence: ${each.value.cost}.",
    "The collector is `essential: false` on purpose, so nothing else will tell you and the API",
    "stays healthy throughout. Check the `otel-collector` log stream in the service's log group",
    "at this timestamp; the EMF record carries `service_instance_id` if one task is at fault.",
  ])
  # D-401: informational. The observability leg is dark while this is firing; app traffic is
  # unaffected. Same admission criterion as `langsmith_ingest_failed`.
  alarm_actions = [aws_sns_topic.alerts_info.arn]
  ok_actions    = [aws_sns_topic.alerts_info.arn]
  tags          = var.tags
}
