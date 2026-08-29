"""E1.1's CloudWatch join: what the *infrastructure* was doing while each k6 trial ran.

A k6 summary says what the client saw. It cannot say whether a p95 came from a saturated CPU,
an exhausted connection pool, or an autoscale event mid-run - and those are different findings.
This reads the run windows out of `run_e1_sweep.sh`'s manifest and pulls ECS, ALB and RDS
metrics over exactly those windows, so every latency number in E1_REPORT.md has the utilization
that produced it beside it.

Read-only: `get_metric_statistics` / `describe_alarm_history` only. Uses the
`jeongsik-staging-admin` profile (the static key pair repo Python reads via plain `AWS_PROFILE`).

**Two things this file exists to get right, both of which have burned a hand-read before.**

1. **Timestamps.** `aws cloudwatch get-metric-statistics` on the CLI prints datapoints in the
   caller's local zone (`-05:00` here) while the run manifest is in UTC, and D-135 §3 already
   recorded one wrong reading that came from exactly that kind of offset. Everything below is
   converted to a UTC ISO string explicitly at the boundary, and the window is echoed into the
   output so a reader can check the join rather than trust it.
2. **Period vs run length.** CloudWatch's minimum standard period is 60 s. A 10-VU burst lasts
   ~10 s, so its "utilization" is a one-minute bucket that is mostly idle - the number is real
   but *diluted*, and reporting it as the load's CPU would overstate the service's headroom.
   Each run therefore records `window_seconds` and `dilution_note`, and the report reads burst
   utilization as an upper bound on idleness rather than as a measurement of the load.

Usage:
    AWS_PROFILE=jeongsik-staging-admin uv run python \\
      benchmarks/resume_evidence/01_platform/collect_e1_cloudwatch.py \\
      --manifest docs/resume_evidence/01_platform/raw/sweep_manifest.jsonl \\
      --out docs/resume_evidence/01_platform/cloudwatch_join.json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3

CLUSTER = "intellichoice-staging"
SERVICE = "intellichoice-staging-learning-api"
# The dimension *values* CloudWatch wants for an ALB are the tail of the ARN, not the name.
LOAD_BALANCER = "app/intellichoice-staging-alb/a1e99fb6d592d3d4"
TARGET_GROUP = "targetgroup/learning-api-tg/91d67e399fbed285"
DB_INSTANCE = "intellichoice-staging-postgres"
P95_ALARM = "intellichoice-staging-learning-api-p95-latency"

# (key, namespace, metric, dimensions, statistics, extended)
METRICS: list[tuple[str, str, str, dict[str, str], list[str], list[str]]] = [
    (
        "ecs_cpu_utilized",
        "ECS/ContainerInsights",
        "CpuUtilized",
        {"ClusterName": CLUSTER, "ServiceName": SERVICE},
        ["Average", "Maximum"],
        [],
    ),
    (
        "ecs_cpu_reserved",
        "ECS/ContainerInsights",
        "CpuReserved",
        {"ClusterName": CLUSTER, "ServiceName": SERVICE},
        ["Average"],
        [],
    ),
    (
        "ecs_memory_utilized_mb",
        "ECS/ContainerInsights",
        "MemoryUtilized",
        {"ClusterName": CLUSTER, "ServiceName": SERVICE},
        ["Average", "Maximum"],
        [],
    ),
    (
        "ecs_running_task_count",
        "ECS/ContainerInsights",
        "RunningTaskCount",
        {"ClusterName": CLUSTER, "ServiceName": SERVICE},
        ["Average", "Maximum", "Minimum"],
        [],
    ),
    (
        "ecs_cpu_percent",
        "AWS/ECS",
        "CPUUtilization",
        {"ClusterName": CLUSTER, "ServiceName": SERVICE},
        ["Average", "Maximum"],
        [],
    ),
    (
        "ecs_memory_percent",
        "AWS/ECS",
        "MemoryUtilization",
        {"ClusterName": CLUSTER, "ServiceName": SERVICE},
        ["Average", "Maximum"],
        [],
    ),
    (
        "alb_target_response_time_s",
        "AWS/ApplicationELB",
        "TargetResponseTime",
        {"LoadBalancer": LOAD_BALANCER, "TargetGroup": TARGET_GROUP},
        ["Average", "Maximum"],
        ["p50", "p95", "p99"],
    ),
    (
        "alb_request_count",
        "AWS/ApplicationELB",
        "RequestCount",
        {"LoadBalancer": LOAD_BALANCER, "TargetGroup": TARGET_GROUP},
        ["Sum"],
        [],
    ),
    (
        "alb_target_5xx",
        "AWS/ApplicationELB",
        "HTTPCode_Target_5XX_Count",
        {"LoadBalancer": LOAD_BALANCER, "TargetGroup": TARGET_GROUP},
        ["Sum"],
        [],
    ),
    (
        "alb_target_4xx",
        "AWS/ApplicationELB",
        "HTTPCode_Target_4XX_Count",
        {"LoadBalancer": LOAD_BALANCER, "TargetGroup": TARGET_GROUP},
        ["Sum"],
        [],
    ),
    (
        "alb_elb_5xx",
        "AWS/ApplicationELB",
        "HTTPCode_ELB_5XX_Count",
        {"LoadBalancer": LOAD_BALANCER},
        ["Sum"],
        [],
    ),
    (
        "rds_connections",
        "AWS/RDS",
        "DatabaseConnections",
        {"DBInstanceIdentifier": DB_INSTANCE},
        ["Average", "Maximum"],
        [],
    ),
    (
        "rds_cpu_percent",
        "AWS/RDS",
        "CPUUtilization",
        {"DBInstanceIdentifier": DB_INSTANCE},
        ["Average", "Maximum"],
        [],
    ),
    (
        # A t4g.micro runs on CPU credits. A sustained run that drains the balance degrades the
        # database for hours afterwards, so this is both a result and an operational check.
        "rds_cpu_credit_balance",
        "AWS/RDS",
        "CPUCreditBalance",
        {"DBInstanceIdentifier": DB_INSTANCE},
        ["Average", "Minimum"],
        [],
    ),
    (
        "rds_freeable_memory_bytes",
        "AWS/RDS",
        "FreeableMemory",
        {"DBInstanceIdentifier": DB_INSTANCE},
        ["Average", "Minimum"],
        [],
    ),
]


# RDS publishes these at 5-minute resolution regardless of what you ask for, so a 60 s period
# over a two-minute burst window returns zero datapoints - which reads as "no data" rather than
# "wrong period", and did on the first run of this collector.
FIVE_MINUTE_METRICS = {"rds_cpu_credit_balance"}


def parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def iso_utc(value: datetime) -> str:
    """The single conversion boundary - see this module's docstring, point 1."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(cw, spec, start: datetime, end: datetime, period: int) -> dict[str, Any]:
    key, namespace, metric, dims, stats, extended = spec
    kwargs: dict[str, Any] = {
        "Namespace": namespace,
        "MetricName": metric,
        "Dimensions": [{"Name": k, "Value": v} for k, v in dims.items()],
        "StartTime": start,
        "EndTime": end,
        "Period": period,
    }
    if stats:
        kwargs["Statistics"] = stats
    if extended:
        kwargs["ExtendedStatistics"] = extended
    points = cw.get_metric_statistics(**kwargs)["Datapoints"]
    points.sort(key=lambda p: p["Timestamp"])
    series = []
    for p in points:
        row: dict[str, Any] = {"t": iso_utc(p["Timestamp"])}
        for s in stats:
            if s in p:
                row[s.lower()] = p[s]
        for name, val in (p.get("ExtendedStatistics") or {}).items():
            row[name] = val
        series.append(row)
    return {
        "metric": f"{namespace}/{metric}",
        "dimensions": dims,
        "period_s": period,
        "datapoints": series,
    }


def summarize(series: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse a window's datapoints into the few numbers a report table can hold."""
    out: dict[str, Any] = {"n_datapoints": len(series)}
    if not series:
        return out
    numeric_keys = {k for row in series for k, v in row.items() if k != "t" and v is not None}
    for k in sorted(numeric_keys):
        vals = [row[k] for row in series if row.get(k) is not None]
        if not vals:
            continue
        out[k] = {
            "min": min(vals),
            "max": max(vals),
            "mean": sum(vals) / len(vals),
            "sum": sum(vals),
        }
    return out


def collect_window(cw, start: datetime, end: datetime, period: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for spec in METRICS:
        if spec[0] in FIVE_MINUTE_METRICS:
            # Widened as well as lengthened: a two-minute burst window can fall entirely
            # between two 5-minute publishes, and an empty series reads as "the database
            # published nothing" rather than "you asked over the wrong window".
            raw = fetch(cw, spec, start - timedelta(minutes=5), end + timedelta(minutes=5), 300)
            raw["window_widened"] = "+/-5 min, 300 s period (RDS publishes this every 5 min)"
        else:
            raw = fetch(cw, spec, start, end, period)
        result[spec[0]] = {**raw, "summary": summarize(raw["datapoints"])}
    return result


def alarm_history(cw, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """The staging p95 alarm is known to fire and self-resolve under load (D-456). Recording the
    transitions is the difference between "an alarm fired, and it was this run" and a mystery
    page later."""
    resp = cw.describe_alarm_history(
        AlarmName=P95_ALARM,
        HistoryItemType="StateUpdate",
        StartDate=start,
        EndDate=end,
        MaxRecords=100,
    )
    return [
        {"t": iso_utc(item["Timestamp"]), "summary": item["HistorySummary"]}
        for item in sorted(resp.get("AlarmHistoryItems", []), key=lambda i: i["Timestamp"])
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--pad-seconds",
        type=int,
        default=60,
        help="widen each run window by this much on both sides; CloudWatch aggregates into "
        "fixed 60 s buckets, so a window that does not cover whole buckets can miss the "
        "bucket the load actually landed in",
    )
    args = ap.parse_args()

    runs = [json.loads(line) for line in open(args.manifest) if line.strip()]
    if not runs:
        raise SystemExit(f"no runs in {args.manifest}")

    cw = boto3.client("cloudwatch", region_name="us-east-1")

    out: dict[str, Any] = {
        "collected_at_utc": iso_utc(datetime.now(UTC)),
        "cluster": CLUSTER,
        "service": SERVICE,
        "db_instance": DB_INSTANCE,
        "note": (
            "All timestamps UTC. CloudWatch's minimum standard period is 60 s, so a burst run "
            "shorter than that reports a bucket that is mostly idle - see per-run "
            "dilution_note."
        ),
        "runs": [],
    }

    for run in runs:
        start = parse_utc(run["started_utc"]) - timedelta(seconds=args.pad_seconds)
        end = parse_utc(run["ended_utc"]) + timedelta(seconds=args.pad_seconds)
        run_seconds = (parse_utc(run["ended_utc"]) - parse_utc(run["started_utc"])).total_seconds()
        period = 60
        entry = {
            "label": run["label"],
            "scenario": run["scenario"],
            "vus": run["vus"],
            "run_started_utc": run["started_utc"],
            "run_ended_utc": run["ended_utc"],
            "run_seconds": run_seconds,
            "query_window_utc": [iso_utc(start), iso_utc(end)],
            "dilution_note": (
                "run shorter than the 60 s CloudWatch period - utilization here is a "
                "mostly-idle bucket, not the load's own utilization"
                if run_seconds < period
                else "run covers at least one full CloudWatch period"
            ),
            "metrics": collect_window(cw, start, end, period),
        }
        out["runs"].append(entry)
        print(f"joined {run['label']}: {iso_utc(start)} .. {iso_utc(end)}", flush=True)

    sweep_start = parse_utc(runs[0]["started_utc"]) - timedelta(minutes=5)
    sweep_end = parse_utc(runs[-1]["ended_utc"]) + timedelta(minutes=5)
    out["sweep_window_utc"] = [iso_utc(sweep_start), iso_utc(sweep_end)]
    out["p95_alarm_history"] = alarm_history(cw, sweep_start, sweep_end)
    out["sweep_window_metrics"] = collect_window(cw, sweep_start, sweep_end, 60)

    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=False)
    print(
        f"wrote {args.out} ({len(out['runs'])} runs, "
        f"{len(out['p95_alarm_history'])} alarm transitions)"
    )


if __name__ == "__main__":
    main()
