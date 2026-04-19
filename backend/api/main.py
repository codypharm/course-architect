"""FastAPI application factory for AI Course Architect.

Mounts all routes under /api/v1. On startup:
  - Loads .env so LANGCHAIN_* and DATABASE_URL are available before any import
  - Creates the uploads/ directory for knowledge base file storage
  - Creates all DB tables (SQLite in Phase 1, Aurora asyncpg in Phase 2)
"""
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # must run before LangChain/LangGraph modules read env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.courses import router as courses_router
from api.routes.files import router as files_router
from graph.graph import _checkpointer
from storage.database import Base, engine

UPLOAD_DIR = Path("uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create uploads dir, DB tables, and Redis checkpoint indexes."""
    UPLOAD_DIR.mkdir(exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Creates the Redis search indexes (checkpoint, checkpoint_write) that
    # AsyncRedisSaver needs before it can store or retrieve any state.
    await _checkpointer.asetup()
    yield


app = FastAPI(
    title="AI Course Architect",
    version="0.1.0",
    description="Multi-agent LangGraph pipeline for generating structured courses from a tutor's knowledge base.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to specific origins in production
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
