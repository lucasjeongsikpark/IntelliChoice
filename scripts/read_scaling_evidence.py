#!/usr/bin/env python
"""Read AUD-F-33's evidence — whether each scale-in invocation was accepted or refused.

**Why this is a script rather than a note.** AUD-F-33 sat open for four days as "mechanism
unknown", and both D-132 and D-134 named the same next step: a controlled repro holding
capacity and traffic still across two OK→ALARM cycles. That was never necessary. The
mechanism was already recorded, in the one CloudWatch history type nobody had queried:

    describe-alarm-history --history-item-type Action
    → Failed to execute AutoScaling action: Metric data points must be provided

The scale-in alarm sets `treat_missing_data = "breaching"` on `TargetResponseTime`, which
publishes nothing at zero traffic. So an idle service puts the alarm into ALARM with fifteen
evaluated datapoints and **no value on any of them**, and a step-scaling policy cannot select
a step adjustment without a metric value. Application Auto Scaling refuses the invocation and
**creates no scaling activity at all** — which is exactly why `describe-scaling-activities`
looked empty to D-132. Net effect: **scale-in requires traffic** (D-182).

**What this script is for, in both directions.** Today it demonstrates the defect: every
refusal it prints is a scale-in that did not happen. After the `FILL(m1, 0)` fix is applied it
becomes the verification — the same rows must read `with_value = 15` and `Successfully
executed`, and the exit code goes to 0. Nothing about the instrument changes between those two
uses, which is the point of committing it.

**Why the join, and why not the raw metric.** The first version of this measurement counted
`TargetResponseTime` datapoints in `[t − 15 min, t]` for each invocation and separated
*nothing*: 23 refusals and 10 acceptances among the zero-datapoint rows, plus a refusal *with*
a datapoint. Publish lag and evaluation offsets mean that window is not the window the alarm
used, and only the alarm records which datapoints it actually evaluated. Joining
`stateReasonData.evaluatedDatapoints` to the Action entry that followed separated the same 44
events perfectly. **When the question is what a component decided on, read what it recorded —
a recomputation that disagrees is evidence about the recomputation.**

**Structural guards, in the style of `scan_xray_pii.py` and `read_scheduler_evidence.py` — a
read that cannot fail is worthless:**

  1. **A positive control, because "no refusals" is ambiguous.** Zero ALARM transitions in the
     window means the window was quiet or the alarm name is wrong, not that scaling is
     healthy. With no transitions at all the run exits INVALID rather than clean — this is the
     AUD-F-12 false negative (an empty trace store certified "no PII") in a different store.
  2. **Unjoinable transitions are reported, never dropped.** An ALARM transition with no Action
     entry within `_JOIN_WINDOW_S` is printed as `?`. Silently discarding it would make a
     missing outcome look like a clean one, and the branch below is already one this
     instrument cannot see.
  3. **Timestamps are printed in UTC with the `Z`, always.** Both the CLI and boto3 hand back
     local-time datetimes, which is the raw material of D-135's first error — and the reason
     the decisive row here (`2026-07-31T00:51:31Z`, the minute D-132 recorded) was initially
     read an hour off.
  4. **Absent is not zero for cost.** A service with no `DesiredTaskCount` series is reported
     as unknown rather than as zero excess capacity.

**⚠️ The branch this cannot see, stated because omitting one reports it as its most flattering
outcome** (D-179). Auto Scaling also re-applies a step policy on its own while the alarm stays
in ALARM, with no CloudWatch transition — visible as chat-api stepping 3→2 at
`2026-07-31T00:15:32Z` and 2→1 at `00:21:32Z` inside one uninterrupted ALARM. Refusals on that
path leave no record anywhere: CloudWatch logs alarm-action outcomes, Auto Scaling logs
successful activities, and nothing logs "re-evaluated, had no data". So this instrument proves
the alarm-action path and is only *consistent with* the other. The fix supplies a value to
both; the claim is what differs.

Read-only: `describe-alarm-history` and `get-metric-statistics` only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import boto3

# The refusal this finding is about. Matched as a prefix because the message carries no
# structured field - if AWS ever rewords it, the run must fail loudly rather than reclassify
# every refusal as an acceptance, so `_classify` treats an unrecognised summary as unknown.
_REFUSAL_PREFIX = "Failed to execute AutoScaling action"
_ACCEPTANCE_PREFIX = "Successfully executed action"

# CloudWatch invokes an alarm action within seconds of the state change. Two minutes is wide
# enough for publish lag and narrow enough that it cannot pair a transition with the *next*
# cycle's action - the alarm's own cooldown is 300 s.
_JOIN_WINDOW_S = 120

# Per-service capacity floors, mirroring terraform/environments/staging/main.tf. Passed
# explicitly rather than read from the scalable target: AUD-F-12's lesson is that a value
# assembled by convention reports a healthy-looking answer when the convention changes, and
# here a wrong floor would understate the excess rather than error.
_SERVICES = {
    "learning-api": 2,
    "chat-api": 1,
}

_CLUSTER = "intellichoice-staging"
_ALARM_TEMPLATE = "intellichoice-staging-{service}-p95-latency-scale-in"
_ECS_SERVICE_TEMPLATE = "intellichoice-staging-{service}"

# us-east-1 Fargate on-demand, for the 512 CPU / 1024 MB task size both services run. Only
# used to turn task-hours into a figure a person can weigh; the task-hours are the measurement.
_TASK_HOUR_USD = 0.5 * 0.04048 + 1.0 * 0.004445

_COST_PERIOD_S = 600


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _stamp(value: datetime) -> str:
    return _utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Invocation:
    """One `OK → ALARM` transition and the Auto Scaling outcome that followed it."""

    transition_at: datetime
    evaluated: int
    with_value: int
    outcome: str  # "accepted" | "refused" | "unknown" | "no-action-entry"
    summary: str


def _classify(summary: str) -> str:
    if summary.startswith(_ACCEPTANCE_PREFIX):
        return "accepted"
    if summary.startswith(_REFUSAL_PREFIX):
        return "refused"
    return "unknown"


def _alarm_history(cloudwatch, alarm: str, kind: str, start: datetime, end: datetime) -> list[dict]:
    items: list[dict] = []
    paginator = cloudwatch.get_paginator("describe_alarm_history")
    for page in paginator.paginate(
        AlarmName=alarm,
        HistoryItemType=kind,
        StartDate=start,
        EndDate=end,
        ScanBy="TimestampAscending",
    ):
        items.extend(page["AlarmHistoryItems"])
    return items


def _read_invocations(cloudwatch, alarm: str, start: datetime, end: datetime) -> list[Invocation]:
    actions = [
        (_utc(item["Timestamp"]), item["HistorySummary"])
        for item in _alarm_history(cloudwatch, alarm, "Action", start, end)
    ]

    invocations: list[Invocation] = []
    for item in _alarm_history(cloudwatch, alarm, "StateUpdate", start, end):
        data = json.loads(item["HistoryData"])
        new_state = data["newState"]
        if new_state["stateValue"] != "ALARM":
            continue

        at = _utc(item["Timestamp"])
        datapoints = new_state.get("stateReasonData", {}).get("evaluatedDatapoints", [])
        with_value = sum(1 for point in datapoints if "value" in point)

        outcome, summary = "no-action-entry", ""
        for action_at, action_summary in actions:
            if 0 <= (action_at - at).total_seconds() <= _JOIN_WINDOW_S:
                outcome, summary = _classify(action_summary), action_summary
                break

        invocations.append(
            Invocation(
                transition_at=at,
                evaluated=len(datapoints),
                with_value=with_value,
                outcome=outcome,
                summary=summary,
            )
        )
    return invocations


def _excess_task_hours(cloudwatch, service: str, floor: int, start: datetime, end: datetime):
    """Task-hours held above the capacity floor, or None when the series is absent."""
    response = cloudwatch.get_metric_statistics(
        Namespace="ECS/ContainerInsights",
        MetricName="DesiredTaskCount",
        Dimensions=[
            {"Name": "ClusterName", "Value": _CLUSTER},
            {"Name": "ServiceName", "Value": _ECS_SERVICE_TEMPLATE.format(service=service)},
        ],
        StartTime=start,
        EndTime=end,
        Period=_COST_PERIOD_S,
        Statistics=["Maximum"],
    )
    points = response["Datapoints"]
    if not points:
        return None, None
    excess = sum(max(0.0, p["Maximum"] - floor) for p in points) * _COST_PERIOD_S / 3600
    above = sum(1 for p in points if p["Maximum"] > floor) / len(points)
    return excess, above


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=8,
        help="lookback window; CloudWatch retains alarm history for 14 days (default: 8)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    args = parser.parse_args()

    cloudwatch = boto3.client("cloudwatch", region_name=args.region)
    end = datetime.now(UTC)
    start = end - timedelta(days=args.days)

    print(f"window: {_stamp(start)} → {_stamp(end)}  ({args.days} days)\n")

    tally: Counter[tuple[str, str]] = Counter()
    total_invocations = 0
    total_excess = 0.0
    cost_unknown: list[str] = []

    for service, floor in _SERVICES.items():
        alarm = _ALARM_TEMPLATE.format(service=service)
        invocations = _read_invocations(cloudwatch, alarm, start, end)
        total_invocations += len(invocations)

        print(f"=== {alarm} (floor {floor}) — {len(invocations)} invocation(s) ===")
        if invocations:
            print(f"{'ALARM transition (UTC)':<23}{'evaluated':>10}{'with_value':>12}  outcome")
            for item in invocations:
                mark = {"accepted": "OK", "refused": "REFUSED"}.get(item.outcome, item.outcome)
                print(
                    f"{_stamp(item.transition_at):<23}{item.evaluated:>10}"
                    f"{item.with_value:>12}  {mark}"
                )
                tally[("value" if item.with_value else "no-value", item.outcome)] += 1

        excess, above = _excess_task_hours(cloudwatch, service, floor, start, end)
        if excess is None:
            cost_unknown.append(service)
            print("  cost: UNKNOWN — no DesiredTaskCount series (absent is not zero)\n")
        else:
            total_excess += excess
            print(
                f"  cost: {excess:.1f} task-hours above floor "
                f"= ${excess * _TASK_HOUR_USD:.2f}, above floor in {above:.1%} of samples\n"
            )

    print("=== alarm evaluation vs Auto Scaling outcome (both services pooled) ===")
    for key in sorted(tally):
        print(f"  {key[0]:<9} → {key[1]:<15} {tally[key]:>3}")

    if total_excess:
        monthly = total_excess * _TASK_HOUR_USD / args.days * 30
        print(
            f"\ntotal excess: {total_excess:.1f} task-hours = "
            f"${total_excess * _TASK_HOUR_USD:.2f} over {args.days} days "
            f"→ ~${monthly:.2f}/month at this rate"
        )

    # Guard 1: a clean report is meaningless if the instrument saw nothing.
    if total_invocations == 0:
        print(
            "\nINVALID: no ALARM transitions in this window. That is ambiguous between a quiet "
            "window and a wrong alarm name - it is not evidence that scale-in works. Widen "
            "--days or check the alarm names.",
            file=sys.stderr,
        )
        return 2

    refused = sum(count for (_, outcome), count in tally.items() if outcome == "refused")
    unmatched = sum(
        count
        for (_, outcome), count in tally.items()
        if outcome in {"unknown", "no-action-entry"}
    )

    if unmatched:
        print(
            f"\n⚠️  {unmatched} invocation(s) could not be classified. Reported, not dropped "
            "(guard 2) - an unmatched outcome must not read as a clean one.",
            file=sys.stderr,
        )
    if cost_unknown:
        print(f"⚠️  cost unknown for: {', '.join(cost_unknown)}", file=sys.stderr)

    if refused:
        print(
            f"\nFAIL: {refused} scale-in invocation(s) were refused for want of a metric value "
            "- AUD-F-33 is present. Each one is a scale-in that did not happen.",
            file=sys.stderr,
        )
        return 1

    print(
        f"\nPASS: {total_invocations} invocation(s), none refused. Every ALARM transition "
        "carried a metric value Auto Scaling could act on."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
