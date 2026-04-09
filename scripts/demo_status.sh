#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.demo-runtime"
HEARTBEAT_FILE="$ROOT_DIR/.daemon_heartbeat"

report_pid() {
  local label="$1"
  local pid_file="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$label: running (pid $pid)"
      return
    fi
  fi
  echo "$label: stopped"
}

report_pid "API" "$RUNTIME_DIR/api.pid"
report_pid "Scheduler" "$RUNTIME_DIR/scheduler.pid"
report_pid "Tunnel" "$RUNTIME_DIR/tunnel.pid"

if [[ -f "$HEARTBEAT_FILE" ]]; then
  last="$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  age=$(( now - ${last%.*} ))
  echo "Scheduler heartbeat: ${age}s ago"
else
  echo "Scheduler heartbeat: unavailable"
fi

echo "Recent pipeline log:"
tail -n 5 "$ROOT_DIR/pipeline_stream.log" 2>/dev/null || true
