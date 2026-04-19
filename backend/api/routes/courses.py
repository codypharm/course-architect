"""Course pipeline routes.

Five endpoints drive the full tutor workflow:

  POST   /courses                              — enqueue pipeline start, return immediately
  GET    /courses/{thread_id}                  — poll current graph state (reads Redis + DB)
  POST   /courses/{thread_id}/validation/resume    — enqueue HITL #1 resume
  POST   /courses/{thread_id}/curriculum/resume    — enqueue HITL #2 resume
  GET    /users/{user_id}/courses              — list all courses for a user (from DB)

All write endpoints return immediately with status="queued" or "processing".
The client polls GET /courses/{thread_id} until status changes to a pause or terminal state.
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.courses import (
    CourseListItem,
    CourseStatusResponse,
    CurriculumResumeRequest,
    StartCourseRequest,
    ValidationResumeRequest,
)
from graph.graph import graph
from utils.pipeline import derive_pipeline_status, graph_config, infer_processing_stage
from celery_app.tasks import pipeline_resume_curriculum, pipeline_resume_validation, pipeline_start
from storage.database import get_db
from storage.models import CourseRecord
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["courses"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_record_or_404(thread_id: str, db: AsyncSession) -> CourseRecord:
    """Fetch CourseRecord by thread_id or raise 404."""
    result = await db.execute(
        select(CourseRecord).where(CourseRecord.thread_id == thread_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail=f"No course found for thread_id={thread_id!r}")
    return record


# ---------------------------------------------------------------------------
# POST /courses
# ---------------------------------------------------------------------------

@router.post("/courses", response_model=CourseStatusResponse, status_code=202)
async def start_course(
    body: StartCourseRequest,
    db: AsyncSession = Depends(get_db),
) -> CourseStatusResponse:
    """Start a new course generation pipeline.

    Upload files first via POST /files and pass their paths in `uploaded_file_paths`.
    Enqueues pipeline_start on the high_priority queue and returns immediately.
    Client should poll GET /courses/{thread_id} until status changes from "queued".
    """
    missing = [p for p in body.uploaded_file_paths if not Path(p).exists()]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"File(s) not found on server: {missing}. Upload via POST /files first.",
        )

    thread_id = str(uuid4())

    record = CourseRecord(
        id=str(uuid4()),
        thread_id=thread_id,
        user_id=body.user_id,
        subject=body.subject,
        status="queued",
        uploaded_files=body.uploaded_file_paths or [],
    )
    db.add(record)
    await db.commit()

    initial_state = {
        "subject": body.subject,
        "audience_age": body.audience_age,
        "audience_level": body.audience_level,
        "duration_weeks": body.duration_weeks,
        "sessions_per_week": body.sessions_per_week,
        "sessions_total": body.sessions_total,
        "preferred_formats": body.preferred_formats,
        "tone": body.tone,
        "include_quiz": body.include_quiz,
        "uploaded_files": body.uploaded_file_paths,
        "enrichment_urls": body.enrichment_urls,
        "additional_context": body.additional_context,
        "retry_count": 0,
        "retry_context": "",
        "retry_history": [],
    }

    pipeline_start.apply_async(args=[thread_id, initial_state])
    logger.info("Enqueued pipeline_start — thread_id=%s subject=%s", thread_id, body.subject)

    return CourseStatusResponse(thread_id=thread_id, status="queued", data={})


# ---------------------------------------------------------------------------
# GET /courses/{thread_id}
# ---------------------------------------------------------------------------

@router.get("/courses/{thread_id}", response_model=CourseStatusResponse)
async def get_course(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
) -> CourseStatusResponse:
    """Poll the current state of a course pipeline run.

    Returns DB status during queued/processing/terminal states.
    When paused at a HITL checkpoint, also returns the interrupt payload
    from live graph state (reads RedisSaver directly).
    """
    record = await _get_record_or_404(thread_id, db)

    # Queued/failed: DB is authoritative, no graph state available
    if record.status in ("queued", "failed"):
        return CourseStatusResponse(thread_id=thread_id, status=record.status, data={})

    # Processing: read graph state to infer which stage the pipeline is currently at
    if record.status == "processing":
        try:
            snapshot = await graph.aget_state(graph_config(thread_id))
            stage = infer_processing_stage(snapshot.values if snapshot else {})
        except Exception:
            stage = 1
        return CourseStatusResponse(
            thread_id=thread_id,
            status="processing",
            data={"processing_stage": stage},
        )

    # For pause/completion statuses, read live graph state for the interrupt payload
    # AsyncRedisSaver only implements async methods — must use aget_state.
    snapshot = await graph.aget_state(graph_config(thread_id))
    if not snapshot or not snapshot.values:
        return CourseStatusResponse(thread_id=thread_id, status=record.status, data={})

    status, data = derive_pipeline_status(snapshot.values, snapshot.next, snapshot.tasks)
    return CourseStatusResponse(thread_id=thread_id, status=status, data=data)


# ---------------------------------------------------------------------------
# POST /courses/{thread_id}/validation/resume
# ---------------------------------------------------------------------------

@router.post("/courses/{thread_id}/validation/resume", response_model=CourseStatusResponse)
async def resume_validation(
    thread_id: str,
    body: ValidationResumeRequest,
    db: AsyncSession = Depends(get_db),
) -> CourseStatusResponse:
    """Submit tutor verdict at HITL #1 (validation feasibility report).

    approved=True  → enqueues pipeline_resume_validation on high_priority queue
                     graph continues: (gap_enrichment →) curriculum_planner → HITL #2
    approved=False → enqueues pipeline_resume_validation on high_priority queue
                     graph routes to END (rejected)

    Returns immediately with status="processing". Poll GET /courses/{thread_id} for result.
    """
    record = await _get_record_or_404(thread_id, db)

    record.status = "processing"
    record.updated_at = datetime.now(timezone.utc)
    await db.commit()

    pipeline_resume_validation.apply_async(args=[thread_id, body.approved])
    logger.info("Enqueued pipeline_resume_validation — thread_id=%s approved=%s", thread_id, body.approved)

    return CourseStatusResponse(thread_id=thread_id, status="processing", data={})


# ---------------------------------------------------------------------------
# POST /courses/{thread_id}/curriculum/resume
# ---------------------------------------------------------------------------

@router.post("/courses/{thread_id}/curriculum/resume", response_model=CourseStatusResponse)
async def resume_curriculum(
    thread_id: str,
    body: CurriculumResumeRequest,
    db: AsyncSession = Depends(get_db),
) -> CourseStatusResponse:
    """Submit tutor verdict at HITL #2 (curriculum review).

    approved=True              → enqueues on generation queue; graph ends, curriculum saved
    approved=False + context   → enqueues on retry queue; curriculum_planner re-runs
                                 with HARD CONSTRAINT injected

    Returns immediately with status="processing". Poll GET /courses/{thread_id} for result.
    """
    if not body.approved and not body.retry_context.strip():
        raise HTTPException(
            status_code=422,
            detail="retry_context is required when approved=False",
        )

    record = await _get_record_or_404(thread_id, db)

    record.status = "processing"
    record.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Route retry requests to the dedicated retry queue
    queue = "retry" if not body.approved else "generation"
    pipeline_resume_curriculum.apply_async(
        args=[thread_id, body.approved, body.retry_context],
        queue=queue,
    )
    logger.info(
        "Enqueued pipeline_resume_curriculum — thread_id=%s approved=%s queue=%s",
        thread_id, body.approved, queue,
    )

    return CourseStatusResponse(thread_id=thread_id, status="processing", data={})


# ---------------------------------------------------------------------------
# GET /users/{user_id}/courses
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}/courses", response_model=list[CourseListItem])
async def list_user_courses(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[CourseListItem]:
    """Return all courses created by a user, newest first.

    Reads from DB — does not hit the graph. Returns empty list if user has no courses.
    """
    result = await db.execute(
        select(CourseRecord)
        .where(CourseRecord.user_id == user_id)
        .order_by(CourseRecord.created_at.desc())
    )
    records = result.scalars().all()

    return [
        CourseListItem(
            thread_id=r.thread_id,
            subject=r.subject,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            curriculum_plan=r.curriculum_plan,
            session_content=r.session_content,
        )
        for r in records
    ]
