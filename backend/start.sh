#!/usr/bin/env bash
# Start all backend services: Redis (Docker), Celery worker, FastAPI
# Must be run from the backend/ directory.

set -e
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'
log()  { echo -e "${GREEN}[start]${RESET} $*"; }
warn() { echo -e "${YELLOW}[start]${RESET} $*"; }
err()  { echo -e "${RED}[start]${RESET} $*"; }

# ── 1. Redis (requires redis-stack for JSON.SET / RedisJSON module) ───────────
REDIS_CONTAINER="redis-dev"
REDIS_IMAGE="redis/redis-stack-server:latest"

# Kill any leftover plain redis:7 containers that lack RedisJSON
if docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | grep -q "^redis "; then
  warn "Stopping plain redis:latest container (lacks RedisJSON — not compatible)..."
  docker stop redis 2>/dev/null || true
fi

if lsof -i :6379 -sTCP:LISTEN -t &>/dev/null; then
  # Port is bound — check if it's our redis-stack container
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${REDIS_CONTAINER}$"; then
    warn "Redis Stack already running (${REDIS_CONTAINER}) — skipping."
  else
    warn "Port 6379 in use by an unknown process — assuming Redis is available."
  fi
elif docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${REDIS_CONTAINER}$"; then
  warn "Redis Stack container exists but stopped — restarting."
  docker start "$REDIS_CONTAINER"
  log "Redis Stack restarted."
else
  log "Starting Redis Stack container (includes RedisJSON)..."
  docker run -d --name "$REDIS_CONTAINER" -p 6379:6379 "$REDIS_IMAGE"
  log "Redis Stack started."
fi

# Give Redis a moment to be ready
sleep 2

# ── 2. Kill any stale Celery workers from a previous run ─────────────────────
STALE=$(pgrep -f "celery_app.worker" 2>/dev/null || true)
if [ -n "$STALE" ]; then
  warn "Killing stale Celery worker processes: $STALE"
  kill $STALE 2>/dev/null || true
  sleep 1
fi

# ── 3. Celery worker (background, logs to celery.log) ────────────────────────
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
