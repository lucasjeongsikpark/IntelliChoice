"""Parse k6 end-of-test summaries into E1.1's sweep table.

One parser for every number that reaches `sweep_metrics.csv` and `E1_REPORT.md`, because the
sweep's whole value is that nine trials are comparable, and nine hand-read summaries are not.

**The one thing that is easy to get exactly backwards.** In k6's legacy summary-export format a
threshold's exported value answers *"did this threshold fail?"* - so `false` means the threshold
**passed**. Verified empirically before the sweep ran, against a run with `MIN_RPS=1000` forced
to breach: the breaching run exported `true`. Reading it as "passed" would invert every
pass/fail in the report while leaving every latency number correct, which is the most
expensive shape of wrong a measurement report can take.

**Rates carry denominators** (MEASUREMENT_PLAN's evidence rules): `http_req_failed` is a k6 Rate
whose `passes` counts the requests that *failed* and whose `fails` counts the ones that
succeeded - the naming follows the metric's own boolean, not the request's fate - so the
success fraction is reconstructed as `fails / (passes + fails)` rather than read off a rate.

Usage:
    python3 benchmarks/resume_evidence/01_platform/k6_summary.py \\
      --manifest docs/resume_evidence/01_platform/raw/sweep_manifest.jsonl \\
      --csv docs/resume_evidence/01_platform/sweep_metrics.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import statistics
from typing import Any

# k6 writes these when a request never completed. Counted from the run log because the summary
# folds timeouts into `http_req_failed` with no separate metric, and "0.4% failed" reads very
# differently depending on whether those were 500s or 60-second hangs.
TIMEOUT_PATTERNS = (
    "context deadline exceeded",
    "request timeout",
    "dial tcp",
    "EOF",
)


def threshold_failed(metric: dict[str, Any], expression: str) -> bool | None:
    """True when the named threshold FAILED. See the module docstring."""
    thresholds = (metric or {}).get("thresholds") or {}
    if expression not in thresholds:
        return None
    return bool(thresholds[expression])


def parse_summary(summary: dict[str, Any]) -> dict[str, Any]:
    m = summary.get("metrics", {})
    dur = m.get("http_req_duration", {}) or {}
    reqs = m.get("http_reqs", {}) or {}
    failed = m.get("http_req_failed", {}) or {}

    n_failed = failed.get("passes", 0)
    n_ok = failed.get("fails", 0)
    total = n_failed + n_ok

    warm_reqs = m.get("http_reqs{phase:warm}") or {}
    cold_reqs = m.get("http_reqs{phase:cold}") or {}
    warm_dur = m.get("http_req_duration{phase:warm}") or {}
    cold_dur = m.get("http_req_duration{phase:cold}") or {}

    return {
        "requests_total": reqs.get("count", total),
        "requests_ok": n_ok,
        "requests_failed": n_failed,
        "success_fraction": f"{n_ok}/{total}" if total else "0/0",
        "success_rate": (n_ok / total) if total else None,
        "rps": reqs.get("rate"),
        "p50_ms": dur.get("p(50)"),
        "p95_ms": dur.get("p(95)"),
        "p99_ms": dur.get("p(99)"),
        "max_ms": dur.get("max"),
        "status_4xx": (m.get("learning_status_4xx") or {}).get("count"),
        "status_5xx": (m.get("learning_status_5xx") or {}).get("count"),
        "answers_submitted": (m.get("learning_answers_submitted") or {}).get("count"),
        "attendance_blocked": (m.get("learning_attendance_blocked") or {}).get("count"),
        "iterations": (m.get("iterations") or {}).get("count"),
        "threshold_p95_failed": threshold_failed(dur, "p(95)<3000"),
        "threshold_error_rate_failed": threshold_failed(failed, "rate<0.01"),
        # Cold/warm only exist on a sustained run; a burst tags everything `warm` by design.
        "cold_requests": cold_reqs.get("count"),
        "warm_requests": warm_reqs.get("count"),
        "cold_p95_ms": cold_dur.get("p(95)") or None,
        "warm_p50_ms": warm_dur.get("p(50)") or None,
        "warm_p95_ms": warm_dur.get("p(95)") or None,
        "warm_p99_ms": warm_dur.get("p(99)") or None,
    }


def count_timeouts(log_path: pathlib.Path) -> int:
    if not log_path.exists():
        return 0
    text = log_path.read_text(errors="replace")
    return sum(len(re.findall(re.escape(p), text)) for p in TIMEOUT_PATTERNS)


def stop_verdict(summary: dict[str, Any]) -> tuple[bool, str]:
    """The sweep's stop rule, as a function.

    Deliberately duplicated as a few lines of inline Python inside `run_e1_sweep.sh`: the runner
    must be able to abort a live staging sweep without depending on this file importing cleanly,
    and an import error mid-sweep that silently disabled the D-455 stop condition would be worse
    than the duplication. `test_e1_sse_ledger.py` pins the two together on shared fixtures.
    """
    m = summary.get("metrics", {})
    fivexx = (m.get("learning_status_5xx") or {}).get("count")
    if fivexx is None:
        return False, "the 5xx counter is absent - the harness did not measure what it claims to"
    if fivexx > 0:
        return False, f"{fivexx} 5xx responses (possible D-455 rotation-class incident)"
    rate = (m.get("http_req_failed") or {}).get("value", 0.0)
    if rate >= 0.01:
        return False, f"http_req_failed rate {rate:.4f} at or above the 1% threshold"
    blocked = (m.get("learning_attendance_blocked") or {}).get("count")
    if blocked:
        return False, f"{blocked} attendance-blocked VUs - stale fixture or a real regression"
    answers = (m.get("learning_answers_submitted") or {}).get("count", 0)
    if answers == 0:
        return False, "zero answers submitted - the run reached no exam and measured nothing"
    return True, "ok"


def level_of(label: str) -> str:
    match = re.search(r"_(\d+)vu", label)
    return match.group(1) if match else ""


def trial_of(label: str) -> str:
    match = re.search(r"_t(\d+)$", label)
    return match.group(1) if match else ""


def group_of(label: str) -> str:
    """The key trials are averaged over - the VU level *and* anything that makes a run
    non-comparable with the others at that level.

    Not the same thing as `level_of`, and the difference is load-bearing: two 10-VU bursts in
    this sweep ran while the service had scaled to **3** tasks rather than 2, and folding them
    into the 10-VU median silently mixed two different systems into one number (it moved the
    median p95 from 1051 ms to 811 ms before this function existed). A label that is not a plain
    `_tN` trial gets its own group, so a run can only ever be averaged with runs it is
    comparable to.
    """
    level = level_of(label)
    if re.search(r"_t\d+$", label):
        return level
    variant = re.sub(r"^burst_\d+vu_", "", label)
    variant = re.sub(r"_[a-z]$", "", variant)
    return f"{level}_{variant}"


def build_rows(manifest_path: pathlib.Path) -> list[dict[str, Any]]:
    rows = []
    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue
        run = json.loads(line)
        summary_path = pathlib.Path(run["summary_path"])
        if not summary_path.is_absolute():
            summary_path = manifest_path.parent.parent.parent.parent / summary_path
        summary = json.loads(pathlib.Path(run["summary_path"]).read_text())
        parsed = parse_summary(summary)
        ok, reason = stop_verdict(summary)
        rows.append(
            {
                "label": run["label"],
                "scenario": run["scenario"],
                "vus": run["vus"],
                "level": level_of(run["label"]),
                "group": group_of(run["label"]),
                "trial": trial_of(run["label"]),
                "duration": run["duration"],
                "started_utc": run["started_utc"],
                "ended_utc": run["ended_utc"],
                "timeouts": count_timeouts(pathlib.Path(run["log_path"])),
                "stop_rule_ok": ok,
                "stop_rule_reason": reason,
                **parsed,
            }
        )
    return rows


def medians(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Median and range across the trials at each burst level - the point of repeating them.

    A median over three trials with the min/max beside it is a claim a reader can check; one
    run's p95 is a number whose repeatability is unknown, which is MEASUREMENT_PLAN Theme 1's
    weakness (4).
    """
    out: dict[str, dict[str, Any]] = {}
    keys = {r["group"] for r in rows if r["scenario"] == "burst"}
    for level in sorted(keys, key=lambda k: (int(k.split("_")[0]), k)):
        group = [r for r in rows if r["scenario"] == "burst" and r["group"] == level]
        entry: dict[str, Any] = {"trials": len(group)}
        for field in ("rps", "p50_ms", "p95_ms", "p99_ms", "success_rate"):
            vals = [r[field] for r in group if r[field] is not None]
            if vals:
                entry[field] = {
                    "median": statistics.median(vals),
                    "min": min(vals),
                    "max": max(vals),
                }
        entry["requests_total"] = sum(r["requests_total"] for r in group)
        entry["requests_ok"] = sum(r["requests_ok"] for r in group)
        entry["status_5xx"] = sum(r["status_5xx"] or 0 for r in group)
        entry["status_4xx"] = sum(r["status_4xx"] or 0 for r in group)
        out[level] = entry
    return out


CSV_FIELDS = [
    "label",
    "scenario",
    "level",
    "trial",
    "vus",
    "duration",
    "started_utc",
    "ended_utc",
    "requests_total",
    "requests_ok",
    "requests_failed",
    "success_fraction",
    "success_rate",
    "rps",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
    "status_4xx",
    "status_5xx",
    "timeouts",
    "answers_submitted",
    "attendance_blocked",
    "iterations",
    "threshold_p95_failed",
    "threshold_error_rate_failed",
    "cold_requests",
    "warm_requests",
    "cold_p95_ms",
    "warm_p50_ms",
    "warm_p95_ms",
    "warm_p99_ms",
    "stop_rule_ok",
    "stop_rule_reason",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--json", default=None, help="also write rows + per-level medians as JSON")
    args = ap.parse_args()

    rows = build_rows(pathlib.Path(args.manifest))
    out = pathlib.Path(args.csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out} ({len(rows)} runs)")

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps({"rows": rows, "per_level": medians(rows)}, indent=2)
        )
        print(f"wrote {args.json}")

    for level, entry in medians(rows).items():
        p95 = entry.get("p95_ms", {})
        rps = entry.get("rps", {})
        print(
            f"  {level:>10} VU x{entry['trials']}: "
            f"rps median={rps.get('median', 0):.2f} "
            f"[{rps.get('min', 0):.2f}-{rps.get('max', 0):.2f}]  "
            f"p95 median={p95.get('median', 0):.0f}ms "
            f"[{p95.get('min', 0):.0f}-{p95.get('max', 0):.0f}]  "
            f"ok={entry['requests_ok']}/{entry['requests_total']}"
        )


if __name__ == "__main__":
    main()
