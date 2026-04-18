"""Celery task definitions for the course generation pipeline.

Each task wraps one segment of the LangGraph graph run:

  pipeline_start             START → validation interrupt (HITL #1)
  pipeline_resume_validation validation resume → curriculum_review interrupt (HITL #2) or END
  pipeline_resume_curriculum curriculum_review resume → END or loop back to curriculum_planner

All tasks:
- Run async LangGraph code via asyncio.run()
- Update CourseRecord status in the DB after each run segment
- Retry up to 3 times with backoff on unexpected failures
"""
import asyncio
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from langgraph.types import Command
from sqlalchemy import select

from graph.graph import graph
from utils.pipeline import derive_pipeline_status, graph_config
from queue.worker import celery_app
from storage.database import AsyncSessionLocal
from storage.models import CourseRecord

logger = get_task_logger(__name__)


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
    await graph.ainvoke(initial_state, config=graph_config(thread_id))
    snapshot = graph.get_state(graph_config(thread_id))
    status, data = derive_pipeline_status(snapshot.values, snapshot.next)
    await _update_db(thread_id, status, data)


async def _run_resume_validation(thread_id: str, approved: bool) -> None:
    """Resume after HITL #1. Runs to HITL #2 or END."""
    await graph.ainvoke(
        Command(resume={"approved": approved}),
        config=graph_config(thread_id),
    )
    snapshot = graph.get_state(graph_config(thread_id))
    status, data = derive_pipeline_status(snapshot.values, snapshot.next)
    await _update_db(thread_id, status, data)


async def _run_resume_curriculum(
    thread_id: str, approved: bool, retry_context: str
) -> None:
    """Resume after HITL #2. Approved → END. Retry → curriculum_planner → HITL #2."""
    await graph.ainvoke(
        Command(resume={"approved": approved, "retry_context": retry_context}),
        config=graph_config(thread_id),
    )
    snapshot = graph.get_state(graph_config(thread_id))
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