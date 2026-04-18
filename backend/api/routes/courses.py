"""Course pipeline routes.

Five endpoints drive the full tutor workflow:

  POST   /courses                              — start pipeline, runs to HITL #1
  GET    /courses/{thread_id}                  — poll current graph state
  POST   /courses/{thread_id}/validation/resume    — resume HITL #1 with approval verdict
  POST   /courses/{thread_id}/curriculum/resume    — resume HITL #2 with review verdict
  GET    /users/{user_id}/courses              — list all courses for a user (from DB)
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command
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
from storage.database import get_db
from storage.models import CourseRecord
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["courses"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(thread_id: str) -> dict:
    """Build the LangGraph config dict for a given thread."""
    return {"configurable": {"thread_id": thread_id}}


def _derive_status(values: dict, paused_at: tuple) -> tuple[str, dict]:
    """Return (status, data) from the graph's current snapshot.

    `paused_at` is LangGraph's state.next — the node(s) currently frozen mid-execution
    by interrupt(). When a node calls interrupt(), it re-appears here because it still
    needs to finish once the client resumes. Falls back to state field values when the
    graph has completed (paused_at is empty).
    """
    paused_set = set(paused_at)

    if "validation" in paused_set:
        return "awaiting_validation", {
            "feasibility_report": values.get("feasibility_report", {}),
            "flags": values.get("flags", []),
            "suggestions": values.get("suggestions", []),
            "estimated_cost_usd": values.get("estimated_cost_usd", 0.0),
        }

    if "curriculum_review" in paused_set:
        return "awaiting_curriculum_review", {
            "curriculum_plan": values.get("curriculum_plan", {}),
            "session_content": values.get("session_content", []),
            "retry_count": values.get("retry_count", 0),
        }

    if values.get("curriculum_approved"):
        return "completed", {
            "curriculum_plan": values.get("curriculum_plan", {}),
            "session_content": values.get("session_content", []),
        }

    # Tutor declined at HITL #1
    return "rejected", {
        "feasibility_report": values.get("feasibility_report", {}),
        "flags": values.get("flags", []),
        "suggestions": values.get("suggestions", []),
    }


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
    Runs the graph until it pauses at HITL #1 (validation feasibility report).
    Returns the thread_id the client must use for all subsequent calls.
    """
    # Validate that every referenced file actually exists on disk
    missing = [p for p in body.uploaded_file_paths if not Path(p).exists()]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"File(s) not found on server: {missing}. Upload via POST /files first.",
        )

    thread_id = str(uuid4())

    # Persist course record immediately so the user can see it even before the
    # pipeline completes the first node
    record = CourseRecord(
        id=str(uuid4()),
        thread_id=thread_id,
        user_id=body.user_id,
        subject=body.subject,
        status="awaiting_validation",
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

    logger.info("Starting course pipeline — thread_id=%s subject=%s", thread_id, body.subject)
    try:
        await graph.ainvoke(initial_state, config=_config(thread_id))
    except Exception as exc:
        # Mark as rejected so the record is not left in a phantom state
        record.status = "rejected"
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        logger.error("Pipeline start error — thread_id=%s: %s", thread_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    snapshot = graph.get_state(_config(thread_id))
    status, data = _derive_status(snapshot.values, snapshot.next)  # snapshot.next = nodes frozen by interrupt()
    return CourseStatusResponse(thread_id=thread_id, status=status, data=data)


# ---------------------------------------------------------------------------
# GET /courses/{thread_id}
# ---------------------------------------------------------------------------

@router.get("/courses/{thread_id}", response_model=CourseStatusResponse)
async def get_course(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
) -> CourseStatusResponse:
    """Return the current state of a course pipeline run.

    Reads live graph state (authoritative) — not the DB snapshot.
    Raises 404 if the thread_id is not found in either source.
    """
    await _get_record_or_404(thread_id, db)   # confirm it exists

    snapshot = graph.get_state(_config(thread_id))
    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail=f"No graph state for thread_id={thread_id!r}")

    status, data = _derive_status(snapshot.values, snapshot.next)  # snapshot.next = nodes frozen by interrupt()
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
    """Resume the pipeline after HITL #1 (validation feasibility report).

    approved=True  → graph continues: (gap_enrichment →) curriculum_planner → HITL #2
    approved=False → graph routes to END (rejected)
    """
    record = await _get_record_or_404(thread_id, db)

    logger.info("Validation resume — thread_id=%s approved=%s", thread_id, body.approved)
    try:
        await graph.ainvoke(
            Command(resume={"approved": body.approved}),
            config=_config(thread_id),
        )
    except Exception as exc:
        logger.error("Validation resume error — thread_id=%s: %s", thread_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    snapshot = graph.get_state(_config(thread_id))
    status, data = _derive_status(snapshot.values, snapshot.next)  # snapshot.next = nodes frozen by interrupt()

    record.status = status
    record.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return CourseStatusResponse(thread_id=thread_id, status=status, data=data)


# ---------------------------------------------------------------------------
# POST /courses/{thread_id}/curriculum/resume
# ---------------------------------------------------------------------------

@router.post("/courses/{thread_id}/curriculum/resume", response_model=CourseStatusResponse)
async def resume_curriculum(
    thread_id: str,
    body: CurriculumResumeRequest,
    db: AsyncSession = Depends(get_db),
) -> CourseStatusResponse:
    """Resume the pipeline after HITL #2 (curriculum review).

    approved=True              → graph ends; full curriculum persisted to DB
    approved=False + context   → curriculum_planner re-runs with HARD CONSTRAINT injected
    """
    if not body.approved and not body.retry_context.strip():
        raise HTTPException(
            status_code=422,
            detail="retry_context is required when approved=False",
        )

    record = await _get_record_or_404(thread_id, db)

    logger.info(
        "Curriculum resume — thread_id=%s approved=%s retry_context=%.60s",
        thread_id, body.approved, body.retry_context,
    )
    try:
        await graph.ainvoke(
            Command(resume={"approved": body.approved, "retry_context": body.retry_context}),
            config=_config(thread_id),
        )
    except Exception as exc:
        logger.error("Curriculum resume error — thread_id=%s: %s", thread_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    snapshot = graph.get_state(_config(thread_id))
    status, data = _derive_status(snapshot.values, snapshot.next)  # snapshot.next = nodes frozen by interrupt()

    record.status = status
    record.updated_at = datetime.now(timezone.utc)

    # Persist the final output when the user approves
    if status == "completed":
        record.curriculum_plan = data.get("curriculum_plan")
        record.session_content = data.get("session_content")

    await db.commit()

    return CourseStatusResponse(thread_id=thread_id, status=status, data=data)


# ---------------------------------------------------------------------------
# GET /users/{user_id}/courses
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}/courses", response_model=list[CourseListItem])
async def list_user_courses(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[CourseListItem]:
    """Return all courses created by a user, newest first.

    Returns an empty list if the user has no courses (not a 404).
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
