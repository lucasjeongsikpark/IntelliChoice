#!/usr/bin/env bash
# Runs the whole local dev stack from one terminal: Postgres/MySQL, both FastAPI
# backends (learning-api :8001, chat-api :8002), and both Vite frontends
# (learning-web :5173, chat-web :5174 - pinned explicitly so they don't collide on
# Vite's shared default port). Ctrl+C stops the four app processes; Postgres/MySQL
# (and the observability containers, if started) are left running - stop those with
# `docker compose down` when you're done for the day.
#
# Usage:
#   ./scripts/dev-up.sh                  # db + both backends + both frontends
#   ./scripts/dev-up.sh --observability  # + otel-collector/jaeger/prometheus/grafana,
#                                          with tracing turned on in both backends
set -uo pipefail
set -m # each backgrounded job below becomes its own process group, so cleanup() can
       # kill an entire `npm run dev` -> vite tree, not just the immediate child.
cd "$(dirname "$0")/.."

WITH_OBSERVABILITY=false
for arg in "$@"; do
  case "$arg" in
    --observability) WITH_OBSERVABILITY=true ;;
    *)
      echo "unknown flag: $arg (only --observability is supported)" >&2
      exit 1
      ;;
  esac
done

LOG_DIR="/tmp/intellichoice-dev-logs"
mkdir -p "$LOG_DIR"
PIDS=()

CLEANED_UP=false
cleanup() {
  $CLEANED_UP && return
  CLEANED_UP=true
  echo ""
  echo "Stopping learning-api / chat-api / learning-web / chat-web..."
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] || continue
    kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "Stopped. Postgres/MySQL$($WITH_OBSERVABILITY && echo '/otel-collector/jaeger/prometheus/grafana') are still running - 'docker compose down' to stop those too."
}
trap cleanup EXIT INT TERM

start() {
  local name="$1" cmd="$2"
  echo "==> $name"
  bash -c "$cmd" >"$LOG_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
}

if $WITH_OBSERVABILITY; then
  echo "==> postgres + mysql + otel-collector + jaeger + prometheus + grafana"
  docker compose up -d postgres mysql otel-collector jaeger prometheus grafana
  export LEARNING_OTEL_ENABLED=true
  export CHAT_OTEL_ENABLED=true
else
  echo "==> postgres + mysql"
  docker compose up -d postgres mysql
fi

start learning-api "uv run uvicorn learning_api.main:app --reload --port 8001"
start chat-api "uv run uvicorn chat_api.main:app --reload --port 8002"

[ -d apps/learning-web/node_modules ] || (cd apps/learning-web && npm install)
[ -d apps/chat-web/node_modules ] || (cd apps/chat-web && npm install)

start learning-web "cd apps/learning-web && npm run dev -- --port 5173"
start chat-web "cd apps/chat-web && npm run dev -- --port 5174"

sleep 2
cat <<EOF

IntelliChoice dev stack is up:
  learning-api   http://localhost:8001   log: $LOG_DIR/learning-api.log
  chat-api       http://localhost:8002   log: $LOG_DIR/chat-api.log
  learning-web   http://localhost:5173   log: $LOG_DIR/learning-web.log
  chat-web       http://localhost:5174   log: $LOG_DIR/chat-web.log
EOF

if $WITH_OBSERVABILITY; then
  cat <<EOF
  jaeger         http://localhost:16686
  prometheus     http://localhost:9090
  grafana        http://localhost:3000
EOF
fi

cat <<EOF

Tail a log:  tail -f $LOG_DIR/<name>.log
Ctrl+C to stop the four app processes above.
EOF

wait
