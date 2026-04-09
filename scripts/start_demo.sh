#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.demo-runtime"
mkdir -p "$RUNTIME_DIR"

cd "$ROOT_DIR"

stop_if_running() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
    fi
    rm -f "$pid_file"
  fi
}

stop_if_running "$RUNTIME_DIR/api.pid"
stop_if_running "$RUNTIME_DIR/scheduler.pid"
stop_if_running "$RUNTIME_DIR/tunnel.pid"

nohup ./venv/bin/python3 -m uvicorn webhook_server:app --host 0.0.0.0 --port 8000 > "$RUNTIME_DIR/api.log" 2>&1 &
echo $! > "$RUNTIME_DIR/api.pid"

nohup ./venv/bin/python3 scheduler.py > "$RUNTIME_DIR/scheduler.log" 2>&1 &
echo $! > "$RUNTIME_DIR/scheduler.pid"

if [[ "${JARVIS_TUNNEL_AUTOSTART:-0}" == "1" ]]; then
  if command -v cloudflared >/dev/null 2>&1; then
    nohup cloudflared tunnel --url http://127.0.0.1:8000 > "$RUNTIME_DIR/tunnel.log" 2>&1 &
    echo $! > "$RUNTIME_DIR/tunnel.pid"
  elif command -v ngrok >/dev/null 2>&1; then
    nohup ngrok http 8000 > "$RUNTIME_DIR/tunnel.log" 2>&1 &
    echo $! > "$RUNTIME_DIR/tunnel.pid"
  else
    echo "[demo] Tunnel autostart requested, but neither cloudflared nor ngrok was found." >&2
  fi
fi

echo "Jarvis demo stack started."
echo "API log:        $RUNTIME_DIR/api.log"
echo "Scheduler log:  $RUNTIME_DIR/scheduler.log"
if [[ -f "$RUNTIME_DIR/tunnel.pid" ]]; then
  echo "Tunnel log:     $RUNTIME_DIR/tunnel.log"
else
  echo "Tunnel:         not started automatically (set JARVIS_TUNNEL_AUTOSTART=1 to enable)"
fi
