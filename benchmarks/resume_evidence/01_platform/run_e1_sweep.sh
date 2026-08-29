#!/usr/bin/env bash
# E1.1 of the resume-evidence measurement program: the repeat-trial + sustained sweep of the
# learning path on deployed staging. See docs/resume_evidence/MEASUREMENT_PLAN.md Theme 1.
#
# Why a runner rather than nine hand-typed `make` lines: the *comparability* of the trials is
# the deliverable. Three trials at one level only mean something if they were run the same way,
# with the same gap between them, and with each run's own UTC window recorded - the window is
# what the CloudWatch join in `collect_e1_cloudwatch.py` later reads ECS/ALB/RDS utilization
# over, and a hand-kept note of "roughly 9:40-ish" cannot be joined to a 60-second metric period.
#
# What it does NOT do: decide anything. It runs the sweep, saves every k6 summary verbatim, and
# stops immediately on a stop condition (below). Interpretation lives in E1_REPORT.md.
#
# **Stop conditions** (D-455): any 5xx, or an `http_req_failed` rate at or above the 1% threshold.
# Staging was force-redeployed 2026-08-29 to mitigate an RDS managed-secret rotation that broke
# *new* DB connections; the next rotation is ~2026-09-04. New-connection database errors appearing
# mid-sweep are the signature of that incident class, and pushing through would both corrupt the
# measurement and delay noticing. A p95 threshold breach is NOT a stop condition - it is the
# result the sweep exists to measure, and D-456 already predicts one at the top of the range.
#
# Load safety: 50 VUs burst / 25 VUs sustained, both inside precedent (D-456 ran 100 VUs bursts
# against this same build with 0 errors). Nothing here raises a Terraform capacity limit or an
# alarm threshold, and the learning path makes no model calls, so model spend is $0.
#
# Usage:
#   AWS_PROFILE=jeongsik-staging-admin benchmarks/resume_evidence/01_platform/run_e1_sweep.sh
#   ... GAP_SECONDS=120 TRIALS=3 SUSTAINED_DURATION=10m OUT_DIR=... (all overridable)
set -uo pipefail
cd "$(dirname "$0")/../../.."   # repository root

OUT_DIR="${OUT_DIR:-docs/resume_evidence/01_platform/raw}"
MANIFEST="${MANIFEST:-$OUT_DIR/sweep_manifest.jsonl}"
GAP_SECONDS="${GAP_SECONDS:-120}"
TRIALS="${TRIALS:-3}"
LEVELS="${LEVELS:-10 25 50}"
SUSTAINED_VUS="${SUSTAINED_VUS:-25}"
SUSTAINED_DURATION="${SUSTAINED_DURATION:-10m}"
: "${AWS_PROFILE:=jeongsik-staging-admin}"
export AWS_PROFILE

mkdir -p "$OUT_DIR"

# Refuse to exceed the spec's ceiling by configuration accident.
MAX_BURST_VUS=50
for lvl in $LEVELS; do
  if [ "$lvl" -gt "$MAX_BURST_VUS" ]; then
    echo "FATAL: level $lvl exceeds the $MAX_BURST_VUS-VU burst ceiling this task is bounded to" >&2
    exit 1
  fi
done
if [ "$SUSTAINED_VUS" -gt 25 ]; then
  echo "FATAL: SUSTAINED_VUS $SUSTAINED_VUS exceeds the 25-VU sustained ceiling" >&2
  exit 1
fi

utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Reads the k6 summary and decides stop / continue. Note the sense of k6's exported threshold
# booleans: in the legacy summary-export format the value is "did this threshold FAIL", so
# `false` means it passed. Verified empirically against a deliberately-failing threshold before
# this sweep was run; getting it backwards would silently invert every pass/fail in the report.
# The stop rule, duplicated from `k6_summary.py:stop_verdict` as dependency-free inline Python
# on purpose: this runner must be able to abort a live staging sweep even if that module cannot
# be imported, and an import error that silently disabled the D-455 guard would be worse than
# the duplication. `test_e1_sse_ledger.py::test_the_runner_and_this_module_apply_the_same_stop_rule`
# executes this exact heredoc against shared fixtures and asserts the two agree.
check_run() {
  python3 - "$1" <<'PY'
import json, sys
path = sys.argv[1]
try:
    m = json.load(open(path))["metrics"]
except Exception as exc:  # a missing summary is itself a failure to measure
    print(f"STOP unreadable summary {path}: {exc}")
    sys.exit(2)
fivexx = m.get("learning_status_5xx", {}).get("count")
failed_rate = m.get("http_req_failed", {}).get("value", 0.0)
reqs = m.get("http_reqs", {}).get("count", 0)
blocked = m.get("learning_attendance_blocked", {}).get("count")
answers = m.get("learning_answers_submitted", {}).get("count", 0)
print(f"requests={reqs} rps={m.get('http_reqs',{}).get('rate',0):.2f} "
      f"failed_rate={failed_rate:.4f} 5xx={fivexx} 4xx={m.get('learning_status_4xx',{}).get('count')} "
      f"blocked={blocked} answers={answers} "
      f"p95={m.get('http_req_duration',{}).get('p(95)',0):.0f}ms")
if fivexx is None:
    print("STOP: the 5xx counter is absent - the harness did not measure what it claims to")
    sys.exit(2)
if fivexx > 0:
    print(f"STOP: {fivexx} 5xx responses (possible D-455 rotation-class incident)")
    sys.exit(2)
if failed_rate >= 0.01:
    print(f"STOP: http_req_failed rate {failed_rate:.4f} at or above the 1% threshold")
    sys.exit(2)
if blocked:
    print(f"STOP: {blocked} attendance-blocked VUs - stale weekly fixture or a real regression")
    sys.exit(2)
if answers == 0:
    print("STOP: zero answers submitted - the run reached no exam and measured nothing")
    sys.exit(2)
PY
}

run_one() {
  local label="$1" scenario="$2" vus="$3" duration="$4"
  local summary="$OUT_DIR/${label}.json"
  # Never silently overwrite a saved trial. A re-run against a populated output directory is
  # almost always a mistake, and the one time it happened it destroyed a completed trial's only
  # copy - the derived tables still quoted numbers whose raw file no longer matched them.
  if [ -e "$summary" ]; then
    echo "FATAL: $summary already exists - refusing to overwrite a saved trial." >&2
    echo "       Move it aside or set OUT_DIR to a fresh directory." >&2
    exit 3
  fi
  local log="$OUT_DIR/${label}.log"
  local started ended
  started="$(utc_now)"
  echo "=== $label  scenario=$scenario vus=$vus duration=$duration  start=$started"
  if [ "$scenario" = "sustained" ]; then
    make load-staging-learning-sustained VUS="$vus" SCENARIO=sustained \
      DURATION="$duration" SUMMARY_OUT="$summary" >"$log" 2>&1
  else
    make load-staging-learning-sustained VUS="$vus" SCENARIO=burst \
      SUMMARY_OUT="$summary" >"$log" 2>&1
  fi
  ended="$(utc_now)"
  local verdict out rc
  out="$(check_run "$summary")"; rc=$?
  echo "$out"
  verdict=$([ $rc -eq 0 ] && echo ok || echo stop)
  python3 - "$MANIFEST" "$label" "$scenario" "$vus" "$duration" "$started" "$ended" "$verdict" "$summary" "$log" <<'PY'
import json, sys
(_, manifest, label, scenario, vus, duration, started, ended, verdict, summary, log) = sys.argv
with open(manifest, "a") as fh:
    fh.write(json.dumps({
        "label": label, "scenario": scenario, "vus": int(vus), "duration": duration,
        "started_utc": started, "ended_utc": ended, "verdict": verdict,
        "summary_path": summary, "log_path": log,
    }) + "\n")
PY
  return $rc
}

echo "E1.1 sweep starting at $(utc_now) (UTC). repo=$(git rev-parse --short HEAD)"
echo "levels='$LEVELS' trials=$TRIALS gap=${GAP_SECONDS}s sustained=${SUSTAINED_VUS}VU/${SUSTAINED_DURATION}"
echo "manifest: $MANIFEST"
echo

# **`seq 1 0` counts DOWN on macOS/BSD** - it prints `1` then `0` rather than nothing - so
# `TRIALS=0`, the obvious way to ask for "sustained leg only", silently ran two more bursts and
# overwrote an existing trial's saved summary. Guarded rather than commented: a runner whose
# job is to protect the integrity of nine comparable trials must not be able to clobber one of
# them because of a shell builtin's edge case.
first=true
for level in $LEVELS; do
  [ "$TRIALS" -ge 1 ] || break
  for trial in $(seq 1 "$TRIALS"); do
    $first || { echo "--- gap ${GAP_SECONDS}s"; sleep "$GAP_SECONDS"; }
    first=false
    if ! run_one "burst_${level}vu_t${trial}" burst "$level" ""; then
      echo "SWEEP ABORTED at burst_${level}vu_t${trial}" >&2
      exit 2
    fi
    echo
  done
done

echo "--- gap ${GAP_SECONDS}s before the sustained run"
sleep "$GAP_SECONDS"
if ! run_one "sustained_${SUSTAINED_VUS}vu_${SUSTAINED_DURATION}" sustained \
     "$SUSTAINED_VUS" "$SUSTAINED_DURATION"; then
  echo "SWEEP ABORTED during the sustained run" >&2
  exit 2
fi

echo
echo "E1.1 sweep complete at $(utc_now) (UTC)."
