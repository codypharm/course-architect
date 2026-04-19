"""Celery task definitions for the course generation pipeline.

Each task wraps one segment of the LangGraph graph run:

  pipeline_start             START → validation interrupt (HITL #1)
  pipeline_resume_validation validation resume → curriculum_review interrupt (HITL #2) or END
  pipeline_resume_curriculum curriculum_review resume → END or loop back to curriculum_planner

All tasks:
- Run async LangGraph code via asyncio.run()
- Create a FRESH AsyncRedisSaver + compiled graph per task invocation so that
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
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.types import Command
from sqlalchemy import select

from graph.graph import build_graph
from utils.pipeline import derive_pipeline_status, graph_config
from celery_app.worker import celery_app
from storage.database import AsyncSessionLocal
from storage.models import CourseRecord

logger = get_task_logger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@asynccontextmanager
async def _fresh_graph():
    """Async context manager that yields a compiled graph with a setup AsyncRedisSaver.

    Using AsyncRedisSaver as an async context manager ensures:
    1. asetup() is called — creates the Redis search indexes (checkpoint,
       checkpoint_write) needed before any ainvoke / aget_state call.
    2. The connection is properly closed on exit.
    3. All connections are bound to the current event loop (each asyncio.run()
       call gets its own loop, so this must be called inside the coroutine).

    Usage::
        async with _fresh_graph() as g:
            await g.ainvoke(...)
    """
    async with AsyncRedisSaver(_REDIS_URL) as checkpointer:
        yield build_graph(checkpointer)


async def _update_db(thread_id: str, status: str, data: dict) -> None:
    """Open a fresh DB session and update the CourseRecord for this thread."""
    async with AsyncSessionLocal() as session:
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

        await session.commit()
        logger.info("DB updated — thread_id=%s status=%s", thread_id, status)


# ---------------------------------------------------------------------------
# Async implementations (called via asyncio.run from Celery tasks)
# ---------------------------------------------------------------------------

async def _run_pipeline_start(thread_id: str, initial_state: dict) -> None:
    """Run graph from START until HITL #1 (validation interrupt)."""
    async with _fresh_graph() as g:
        await g.ainvoke(initial_state, config=graph_config(thread_id))
        snapshot = await g.aget_state(graph_config(thread_id))
    status, data = derive_pipeline_status(snapshot.values, snapshot.next)
    await _update_db(thread_id, status, data)


async def _run_resume_validation(thread_id: str, approved: bool) -> None:
    """Resume after HITL #1. Runs to HITL #2 or END."""
    async with _fresh_graph() as g:
        await g.ainvoke(
            Command(resume={"approved": approved}),
            config=graph_config(thread_id),
        )
        snapshot = await g.aget_state(graph_config(thread_id))
    status, data = derive_pipeline_status(snapshot.values, snapshot.next)
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
    status, data = derive_pipeline_status(snapshot.values, snapshot.next)
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