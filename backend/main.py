"""Entrypoint — runs the FastAPI app with uvicorn.

Production (Fargate): override host/port via environment or the Fargate task
definition command. The `app` object is also importable directly for ASGI
servers that expect `module:app` syntax.
"""
import uvicorn

from api.main import app  # noqa: F401 — re-exported for `uvicorn backend.main:app`

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
