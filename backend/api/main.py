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
from graph.graph import open_checkpointer, close_checkpointer
from storage.database import Base, engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables, open Postgres checkpoint pool, create S3 Vectors index."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Open the psycopg connection pool and create LangGraph checkpoint tables (idempotent).
    # For local dev (MemorySaver) this is a no-op.
    await open_checkpointer()
    # Create the S3 Vectors index if it does not already exist (idempotent).
    from storage.s3vectors import ensure_index
    ensure_index()
    yield
    await close_checkpointer()


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

# Root
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
            "get_course_brief":    "GET  /api/v1/courses/{thread_id}/brief",
            "validation_resume":   "POST /api/v1/courses/{thread_id}/validation/resume",
            "curriculum_resume":   "POST /api/v1/courses/{thread_id}/curriculum/resume",
            "list_user_courses":   "GET  /api/v1/users/{user_id}/courses",
            "delete_course":       "DELETE /api/v1/courses/{thread_id}",
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
