# ── Stage 1: dependency installer ──────────────────────────────────────────────
FROM python:3.13-slim AS deps

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy only the dependency manifest first so Docker cache is reused on code-only changes
COPY backend/pyproject.toml backend/uv.lock* ./

# Install into a venv at /app/.venv
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime image ──────────────────────────────────────────────────────
FROM python:3.13-slim AS final

WORKDIR /app

# Copy the venv from the deps stage
COPY --from=deps /app/.venv /app/.venv

# Copy application source
COPY backend/ .

# Add /app to PYTHONPATH so `from api.xxx import` and `from graph.xxx import` resolve correctly
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"

# Expose FastAPI port (overridden for Celery services — they don't listen)
EXPOSE 8000

# Default entry point — overridden per ECS task definition:
#   API:    uvicorn api.main:app --host 0.0.0.0 --port 8000
#   Worker: celery -A celery_app.worker worker -Q high_priority,generation,retry --loglevel=info
#   Beat:   celery -A celery_app.worker beat --loglevel=info
#   Flower: celery -A celery_app.worker flower --port=5555
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
