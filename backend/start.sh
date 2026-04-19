#!/usr/bin/env bash
# Start all backend services: Redis (Docker), Celery worker, FastAPI
# Must be run from the backend/ directory.

set -e
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'
log()  { echo -e "${GREEN}[start]${RESET} $*"; }
warn() { echo -e "${YELLOW}[start]${RESET} $*"; }
err()  { echo -e "${RED}[start]${RESET} $*"; }

# ── 1. Redis ──────────────────────────────────────────────────────────────────
REDIS_CONTAINER="redis-dev"

# Check if port 6379 is already bound (any process or container)
if lsof -i :6379 -sTCP:LISTEN -t &>/dev/null; then
  warn "Port 6379 already in use — Redis is running, skipping."
elif docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${REDIS_CONTAINER}$"; then
  warn "Redis container '${REDIS_CONTAINER}' exists but stopped — restarting."
  docker start "$REDIS_CONTAINER"
  log "Redis restarted."
else
  log "Starting Redis container..."
  docker run -d --name "$REDIS_CONTAINER" -p 6379:6379 redis:7
  log "Redis started."
fi

# Give Redis a moment to be ready
sleep 1

# ── 2. Celery worker (background, logs to celery.log) ────────────────────────
log "Starting Celery worker (logs → celery.log)..."
uv run celery -A celery_app.worker worker \
  -Q high_priority,generation,retry \
  --loglevel=info \
  --logfile=celery.log &
CELERY_PID=$!
log "Celery worker PID: ${CELERY_PID}"

# ── 3. FastAPI ────────────────────────────────────────────────────────────────
log "Starting FastAPI on http://localhost:8000 ..."
log "Celery logs: tail -f $(pwd)/celery.log"
log "Press Ctrl+C to stop everything."

# Trap Ctrl+C to kill Celery worker too
cleanup() {
  echo ""
  warn "Shutting down..."
  kill "$CELERY_PID" 2>/dev/null || true
  log "Done."
}
trap cleanup INT TERM

uv run uvicorn api.main:app --reload --port 8000
