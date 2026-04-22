"""Celery task definitions for the course generation pipeline.

Each task wraps one segment of the LangGraph graph run:

  pipeline_start             START → validation interrupt (HITL #1)
  pipeline_resume_validation validation resume → curriculum_review interrupt (HITL #2) or END
  pipeline_resume_curriculum curriculum_review resume → END or loop back to curriculum_planner

All tasks:
- Run async LangGraph code via asyncio.run()
- Create a FRESH checkpointer + compiled graph per task invocation so that
  connections are always bound to the current event loop.  The module-level
  graph singleton in graph.py is for the FastAPI process only; importing and
  reusing it here would cause "Event loop is closed" errors on Celery retry
  because asyncio.run() creates a new event loop each call.
- Update CourseRecord status in the DB after each run segment
- Retry up to 3 times with backoff on unexpected failures
"""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from graph.graph import build_graph
from utils.pipeline import derive_pipeline_status, graph_config
from celery_app.worker import celery_app
from storage.database import DATABASE_URL, _is_postgres as _db_is_postgres, _is_sqlite
from storage.models import CourseRecord

logger = get_task_logger(__name__)

_is_postgres = DATABASE_URL.startswith("postgresql")
if _is_postgres:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    _PG_CONN_STR = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    if os.getenv("DB_HOST"):
        _PG_CONN_STR += "?sslmode=require"

# Dedicated engine for Celery tasks — uses NullPool (no connection reuse).
# Each Celery task calls asyncio.run() which creates a NEW event loop.  The
# module-level engine in database.py has an asyncpg pool whose connections are
# bound to whichever loop was current on first use.  Reusing those connections
# in a different loop raises "Future attached to a different loop".
# NullPool creates a fresh connection per session.open() and closes it on
# session.close(), so every asyncio.run() call gets connections on its own loop.
_celery_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool,
    connect_args=(
        {"check_same_thread": False} if _is_sqlite
        else {"ssl": "require"} if _db_is_postgres
        else {}
    ),
)
_CelerySession = async_sessionmaker(_celery_engine, expire_on_commit=False)


@asynccontextmanager
async def _fresh_graph():
    """Async context manager yielding a compiled graph with a fresh checkpointer.

    Each Celery task calls asyncio.run(), which creates a new event loop, so
    the checkpointer connection must be created inside the coroutine.

    - Postgres (ECS): AsyncPostgresSaver opened as an async context manager so
      the psycopg connection pool is properly closed on exit.
    - SQLite (local dev): MemorySaver — no connection needed, state lives only
      for the duration of the task run.

    Usage::
        async with _fresh_graph() as g:
            await g.ainvoke(...)
    """
    if _is_postgres:
        async with AsyncPostgresSaver.from_conn_string(_PG_CONN_STR) as checkpointer:
            await checkpointer.setup()
            yield build_graph(checkpointer)
    else:
        from langgraph.checkpoint.memory import MemorySaver
        yield build_graph(MemorySaver())


def _delete_thread_vectors(thread_id: str) -> None:
    """Delete all S3 Vectors for a pipeline run.

    Called at every terminal state (completed, rejected, failed).
    A revised brief gets a new thread_id, so the old run's vectors are
    orphaned and must be cleaned up here.
    """
    try:
        from storage.s3vectors import delete_thread_vectors
        delete_thread_vectors(thread_id)
    except Exception:
        logger.warning(
            "Failed to delete S3 Vectors for thread_id=%s", thread_id, exc_info=True
        )


def _delete_uploaded_files(paths: list[str], thread_id: str) -> None:
    """Delete uploaded files from S3.

    Accepts S3 keys (``uploads/{batch_id}/{filename}``) stored in
    CourseRecord.uploaded_files.  Any entry that is not an S3 key (e.g. a
    legacy local path from dev) is silently skipped.
    """
    from storage.s3 import delete_keys

    s3_keys = [p for p in (paths or []) if p.startswith("uploads/")]
    if not s3_keys:
        return
    try:
        delete_keys(s3_keys)
        logger.info(
            "Deleted %d S3 object(s) for thread_id=%s", len(s3_keys), thread_id
        )
    except Exception:
        logger.warning(
            "Failed to delete S3 objects for thread_id=%s", thread_id, exc_info=True
        )


async def _update_db(thread_id: str, status: str, data: dict) -> None:
    """Open a fresh DB session and update the CourseRecord for this thread.

    On rejection or failure, deletes uploaded files from disk to avoid
    accumulating orphaned files in storage.
    """
    async with _CelerySession() as session:
        result = await session.execute(
            select(CourseRecord).where(CourseRecord.thread_id == thread_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            logger.error("CourseRecord not found for thread_id=%s", thread_id)
            return

        record.status = status
        record.updated_at = datetime.now(timezone.utc)

        if status == "completed":
            record.curriculum_plan = data.get("curriculum_plan")
            record.session_content = data.get("session_content")

        # Only delete uploaded files on hard failure — rejected means the tutor
        # is revising and the uploaded files are still needed for the new run.
        if status == "failed":
            _delete_uploaded_files(record.uploaded_files or [], thread_id)

        await session.commit()

    # Always clean up S3 Vectors at terminal states regardless of DB outcome.
    # Vectors are scoped to thread_id; a revised brief uses a new thread_id
    # and re-ingests the files, so old vectors are always safe to delete.
    if status in ("completed", "rejected", "failed"):
        _delete_thread_vectors(thread_id)
        logger.info("DB updated — thread_id=%s status=%s", thread_id, status)


# ---------------------------------------------------------------------------
# Async implementations (called via asyncio.run from Celery tasks)
# ---------------------------------------------------------------------------

async def _run_pipeline_start(thread_id: str, initial_state: dict) -> None:
    """Run graph from START until HITL #1 (validation interrupt)."""
    async with _fresh_graph() as g:
        await g.ainvoke(initial_state, config=graph_config(thread_id))
        snapshot = await g.aget_state(graph_config(thread_id))
    status, data = derive_pipeline_status(snapshot.values, snapshot.next, snapshot.tasks)
    await _update_db(thread_id, status, data)


async def _run_resume_validation(thread_id: str, approved: bool) -> None:
    """Resume after HITL #1. Runs to HITL #2 or END."""
    async with _fresh_graph() as g:
        await g.ainvoke(
            Command(resume={"approved": approved}),
            config=graph_config(thread_id),
        )
        snapshot = await g.aget_state(graph_config(thread_id))
    status, data = derive_pipeline_status(snapshot.values, snapshot.next, snapshot.tasks)
    await _update_db(thread_id, status, data)


async def _run_resume_curriculum(
    thread_id: str, approved: bool, retry_context: str
) -> None:
    """Resume after HITL #2. Approved → END. Retry → curriculum_planner → HITL #2."""
    async with _fresh_graph() as g:
        await g.ainvoke(
            Command(resume={"approved": approved, "retry_context": retry_context}),
            config=graph_config(thread_id),
        )
        snapshot = await g.aget_state(graph_config(thread_id))
    status, data = derive_pipeline_status(snapshot.values, snapshot.next, snapshot.tasks)
    await _update_db(thread_id, status, data)


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="queue.tasks.pipeline_start", max_retries=3)
def pipeline_start(self, thread_id: str, initial_state: dict) -> None:
    """Queue: high_priority. Runs START → validation HITL #1."""
    logger.info("pipeline_start — thread_id=%s", thread_id)
    try:
        asyncio.run(_run_pipeline_start(thread_id, initial_state))
    except Exception as exc:
        logger.error("pipeline_start failed — thread_id=%s: %s", thread_id, exc, exc_info=True)
        asyncio.run(_update_db(thread_id, "failed", {}))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(bind=True, name="queue.tasks.pipeline_resume_validation", max_retries=3)
def pipeline_resume_validation(self, thread_id: str, approved: bool) -> None:
    """Queue: high_priority. Resumes after HITL #1 verdict."""
    logger.info("pipeline_resume_validation — thread_id=%s approved=%s", thread_id, approved)
    try:
        asyncio.run(_run_resume_validation(thread_id, approved))
    except Exception as exc:
        logger.error(
            "pipeline_resume_validation failed — thread_id=%s: %s", thread_id, exc, exc_info=True
        )
        asyncio.run(_update_db(thread_id, "failed", {}))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(bind=True, name="queue.tasks.pipeline_resume_curriculum", max_retries=3)
def pipeline_resume_curriculum(
    self, thread_id: str, approved: bool, retry_context: str
) -> None:
    """Queue: generation (approval) or retry (retry). Resumes after HITL #2 verdict."""
    logger.info(
        "pipeline_resume_curriculum — thread_id=%s approved=%s",
        thread_id, approved,
    )
    try:
        asyncio.run(_run_resume_curriculum(thread_id, approved, retry_context))
    except Exception as exc:
        logger.error(
            "pipeline_resume_curriculum failed — thread_id=%s: %s", thread_id, exc, exc_info=True
        )
        asyncio.run(_update_db(thread_id, "failed", {}))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)