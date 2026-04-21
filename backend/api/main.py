"""FastAPI application factory for AI Course Architect.

Mounts all routes under /api/v1. On startup:
  - Loads .env so LANGCHAIN_* and DATABASE_URL are available before any import
  - Creates all DB tables via Base.metadata.create_all (Aurora or SQLite, idempotent)
  - Creates LangGraph checkpoint tables (Postgres) or no-ops (MemorySaver for local dev)
  - Creates S3 Vectors index for RAG pipeline (idempotent)
"""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # must run before LangChain/LangGraph modules read env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.courses import router as courses_router
from api.routes.files import router as files_router
from graph.graph import _checkpointer
from storage.database import Base, engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables, Redis checkpoint indexes, and S3 Vectors index."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # AsyncPostgresSaver.setup() creates the checkpoint tables (idempotent).
    # MemorySaver (local dev) has no setup method — the hasattr guard handles that.
    if hasattr(_checkpointer, "setup"):
        await _checkpointer.setup()
    # Create the S3 Vectors index if it does not already exist (idempotent).
    from storage.s3vectors import ensure_index
    ensure_index()
    yield


app = FastAPI(
    title="AI Course Architect",
    version="0.1.0",
    description="Multi-agent LangGraph pipeline for generating structured courses from a tutor's knowledge base.",
    lifespan=lifespan,
)

_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root — human-readable entry point
@app.get("/", tags=["meta"])
async def root():
    """API home. Lists available route groups."""
    return {
        "name": "AI Course Architect API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "start_course":        "POST /api/v1/courses",
            "get_course":          "GET  /api/v1/courses/{thread_id}",
            "validation_resume":   "POST /api/v1/courses/{thread_id}/validation/resume",
            "curriculum_resume":   "POST /api/v1/courses/{thread_id}/curriculum/resume",
            "list_user_courses":   "GET  /api/v1/users/{user_id}/courses",
            "upload_files":        "POST /api/v1/files",
        },
    }


# Health check — no /api/v1 prefix so ALB probes can hit it directly
@app.get("/health", tags=["health"])
async def health_check():
    """ALB / container health probe. Returns 200 when the server is ready."""
    return {"status": "ok", "version": "0.1.0"}


app.include_router(courses_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
