#!/usr/bin/env bash
# Run the full AI Database Agent stack (offline-friendly) with one command.
#
#   ./run.sh            -> checks + backend (:8000) + frontend (:5173)
#   ./run.sh --cli      -> single CLI question mode: ./run.sh --cli "your question"
#   ./run.sh --chat     -> interactive CLI chat with memory
#   ./run.sh --backend  -> backend only
#   ./run.sh --frontend -> frontend only (expects backend already running)
#   ./run.sh --check    -> environment checks only, starts nothing
#
# Ctrl-C stops everything started by this script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  for pid in $FRONTEND_PID $BACKEND_PID; do
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

port_in_use() {
  (command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1) || \
  (command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "$1" >/dev/null 2>&1)
}

check_env() {
  echo "==> Checks"
  [ -d "$ROOT/.venv" ] || { echo "No .venv found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2; exit 1; }
  [ -f "$ROOT/.env" ] || { echo "No .env found. Run: cp .env.example .env" >&2; exit 1; }
  [ -f "$ROOT/data/concert_singer.sqlite" ] || {
    echo "Database missing, building it..."
    "$ROOT/.venv/bin/python" scripts/setup_db.py
  }
  if ! curl -s --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "WARNING: Ollama is not reachable at http://localhost:11434" >&2
    echo "Start it with: ollama serve  (then: ollama pull qwen2.5-coder:7b && ollama pull qwen3.5:4b-mlx)" >&2
  else
    echo "Ollama: reachable"
    "$ROOT/.venv/bin/python" -c "
from ai_database_agent.llm.client import check_ollama_connection, llm_answer_model_name, llm_sql_model_name
print('SQL model:', llm_sql_model_name())
print('Answer model:', llm_answer_model_name())
print(check_ollama_connection()[1])
" 2>/dev/null | grep -v -E 'trace_id|span_id' || true
  fi
  echo "Database: data/concert_singer.sqlite OK"
}

wait_for_url() {
  local url="$1" tries=30
  for _ in $(seq 1 $tries); do
    if curl -s --max-time 2 "$url" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  echo "Timed out waiting for $url" >&2
  return 1
}

start_backend() {
  if port_in_use "$BACKEND_PORT"; then
    echo "Backend port $BACKEND_PORT already in use, reusing it."
    return 0
  fi
  echo "==> Backend on http://localhost:$BACKEND_PORT"
  "$ROOT/.venv/bin/python" -m uvicorn backend.main:app --port "$BACKEND_PORT" --reload &
  BACKEND_PID="$!"
  wait_for_url "http://localhost:$BACKEND_PORT/health"
  echo "Backend ready (/health, /llm/health, /schema, /ask)"
}

start_frontend() {
  if port_in_use "$FRONTEND_PORT"; then
    echo "Frontend port $FRONTEND_PORT already in use, reusing it."
    return 0
  fi
  need_cmd npm
  if [ ! -d "$ROOT/frontend/react-app/node_modules" ]; then
    echo "Installing frontend deps (first time)..."
    (cd "$ROOT/frontend/react-app" && npm install)
  fi
  echo "==> Frontend on http://localhost:$FRONTEND_PORT"
  (cd "$ROOT/frontend/react-app" && PORT="$FRONTEND_PORT" npm run dev -- --port "$FRONTEND_PORT") &
  FRONTEND_PID="$!"
  wait_for_url "http://localhost:$FRONTEND_PORT"
  echo "Frontend ready"
}

MODE="${1:-all}"
case "$MODE" in
  --check)
    check_env
    ;;
  --cli)
    shift
    check_env
    exec "$ROOT/.venv/bin/python" main.py "$@"
    ;;
  --chat)
    check_env
    exec "$ROOT/.venv/bin/python" main.py --chat
    ;;
  --backend)
    check_env
    start_backend
    echo "Backend only. Press Ctrl-C to stop."
    wait
    ;;
  --frontend)
    start_frontend
    echo "Frontend only. Press Ctrl-C to stop."
    wait
    ;;
  all|--all|"")
    check_env
    start_backend
    start_frontend
    echo ""
    echo "All running: frontend http://localhost:$FRONTEND_PORT  |  backend http://localhost:$BACKEND_PORT"
    echo "Press Ctrl-C to stop both."
    wait
    ;;
  --help|-h)
    sed -n '2,14p' "$0"
    ;;
  *)
    echo "Unknown option: $MODE (try --help)" >&2
    exit 1
    ;;
esac
