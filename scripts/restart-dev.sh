#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# Optional CLI (also respected: pre-exported env):
#   --debug-stream              → NEXT_PUBLIC_STREAM_DEBUG=1
#   --save-user-memory          → NEXT_PUBLIC_SAVE_USER_MESSAGE_AS_MEMORY=1
#   --no-conversation-db        → NEXT_PUBLIC_CONVERSATION_DB=off
for _arg in "$@"; do
  case "$_arg" in
    --debug-stream) export NEXT_PUBLIC_STREAM_DEBUG=1 ;;
    --save-user-memory) export NEXT_PUBLIC_SAVE_USER_MESSAGE_AS_MEMORY=1 ;;
    --no-conversation-db) export NEXT_PUBLIC_CONVERSATION_DB=off ;;
  esac
done

BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
FRONTEND_EXTRA_PORTS="${FRONTEND_EXTRA_PORTS:-3000}"
HOST="${HOST:-127.0.0.1}"

BACKEND_LOG="${BACKEND_LOG:-$BACKEND_DIR/backend_log.txt}"
FRONTEND_LOG="${FRONTEND_LOG:-$FRONTEND_DIR/frontend_log.txt}"

log() {
  printf '[dev-restart] %s\n' "$*"
}

sanitize_proxy_env() {
  # Avoid leaking corporate/dev proxy vars into local dev services.
  unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
  export NO_PROXY="127.0.0.1,localhost,::1"
  export no_proxy="$NO_PROXY"
  log "proxy env sanitized for local dev (NO_PROXY=$NO_PROXY)"
}

# Any TCP state on the port (LISTEN, CLOSED, etc.); LISTEN-only misses stuck uvicorn reloaders.
# lsof exits 1 when nothing matches; with pipefail that must not abort the script.
pids_on_port() {
  { lsof -nP -tiTCP:"$1" 2>/dev/null || true; } | sort -u
}

kill_port() {
  local port="$1"
  local pids
  pids="$(pids_on_port "$port" | xargs)"
  if [[ -z "$pids" ]]; then
    log "port $port is free"
    return
  fi

  log "stopping processes on port $port: $pids"
  for pid in $pids; do
    pkill -TERM -P "$pid" 2>/dev/null || true
  done
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  for _ in $(seq 1 10); do
    pids="$(pids_on_port "$port" | xargs)"
    [[ -z "$pids" ]] && break
    sleep 0.3
  done

  pids="$(pids_on_port "$port" | xargs)"
  if [[ -n "$pids" ]]; then
    log "force stopping processes on port $port: $pids"
    for pid in $pids; do
      pkill -KILL -P "$pid" 2>/dev/null || true
    done
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

backend_python() {
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT_DIR/.venv/bin/python"
  elif [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
    printf '%s\n' "$BACKEND_DIR/.venv/bin/python"
  else
    printf '%s\n' "python"
  fi
}

start_backend() {
  local py
  py="$(backend_python)"
  : > "$BACKEND_LOG"
  log "starting backend: http://$HOST:$BACKEND_PORT"
  (
    cd "$BACKEND_DIR"
    "$py" -m uvicorn app.main:app --reload --host "$HOST" --port "$BACKEND_PORT"
  ) >> "$BACKEND_LOG" 2>&1 &
  log "backend pid: $! (log: $BACKEND_LOG)"
}

start_frontend() {
  : > "$FRONTEND_LOG"
  log "starting frontend: http://$HOST:$FRONTEND_PORT"
  (
    cd "$FRONTEND_DIR"
    HOST="$HOST" npx next dev -H "$HOST" -p "$FRONTEND_PORT"
  ) >> "$FRONTEND_LOG" 2>&1 &
  log "frontend pid: $! (log: $FRONTEND_LOG)"
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"

  for _ in $(seq 1 "$attempts"); do
    if curl --max-time 2 -fsS "$url" >/dev/null 2>&1; then
      log "$name is ready: $url"
      return 0
    fi
    sleep 1
  done

  log "$name did not become ready: $url"
  return 1
}

main() {
  log "root: $ROOT_DIR"
  sanitize_proxy_env
  kill_port "$BACKEND_PORT"
  for p in $FRONTEND_EXTRA_PORTS; do
    [[ "$p" == "$FRONTEND_PORT" ]] || kill_port "$p"
  done
  kill_port "$FRONTEND_PORT"

  start_backend
  start_frontend

  wait_for_http "backend" "http://$HOST:$BACKEND_PORT/api/health/live" 30 || {
    log "backend log tail:"
    tail -40 "$BACKEND_LOG" || true
    exit 1
  }

  wait_for_http "frontend" "http://$HOST:$FRONTEND_PORT/" 45 || {
    log "frontend log tail:"
    tail -60 "$FRONTEND_LOG" || true
    exit 1
  }

  log "ready"
  log "frontend: http://$HOST:$FRONTEND_PORT"
  log "backend:  http://$HOST:$BACKEND_PORT"
}

main "$@"
