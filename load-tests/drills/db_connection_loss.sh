#!/usr/bin/env bash
# S34 / SPEC §6.23 "Database failover" drill, translated to what's actually real here:
# staging RDS is single-AZ (multi_az=false, D-084's cost posture), so there is no live
# Multi-AZ failover target to test against this session (no AWS access either - see
# ../README.md). This is the honest local substitute: kill the app's one Postgres
# connection point mid-load and confirm (a) in-flight requests fail cleanly (5xx, not a
# hang or a crash) rather than silently corrupting data, and (b) the app recovers on its
# own once Postgres comes back, with no restart needed (SQLAlchemy's pool reconnects).
#
# Requires: learning-api running locally (`make dev-learning`), Postgres in docker-compose
# already up and migrated. Run from the repo root: ./load-tests/drills/db_connection_loss.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"
HOLD_SECONDS="${HOLD_SECONDS:-20}"

echo "== Starting background SSE load (proxy for in-flight traffic) =="
uv run python load-tests/sse_load.py --base-url "$BASE_URL" --count 20 --hold-seconds "$HOLD_SECONDS" &
LOAD_PID=$!

sleep 5
echo "== Stopping Postgres mid-load =="
docker compose stop postgres
STOPPED_AT=$(date +%s)

echo "== Probing /healthz (liveness-only) vs /readyz (S34's new DB-aware check) while Postgres is down =="
for _ in 1 2 3; do
  curl -s -o /dev/null -w "healthz -> %{http_code}  " "$BASE_URL/healthz" || true
  curl -s -o /dev/null -w "readyz -> %{http_code}\n" "$BASE_URL/readyz" || true
  sleep 2
done

echo "== Restarting Postgres =="
docker compose start postgres
RESTARTED_AT=$(date +%s)
echo "Postgres was down for $((RESTARTED_AT - STOPPED_AT))s"

echo "== Waiting for /readyz to recover on its own (no app restart) =="
for i in $(seq 1 15); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/readyz" || echo "000")
  echo "  attempt $i: readyz -> $CODE"
  if [ "$CODE" = "200" ]; then
    echo "Recovered after ~$((i * 2))s without an app restart."
    break
  fi
  sleep 2
done

wait "$LOAD_PID" || echo "(background SSE load exited non-zero - expected if connections were open when Postgres dropped)"
echo "== Drill complete - review output above for clean 5xx/timeout behavior during the outage, not hangs or 200s with corrupted data =="
