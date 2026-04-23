"""Pydantic request and response schemas for the courses API."""
from datetime import datetime

from pydantic import BaseModel, Field


class StartCourseRequest(BaseModel):
    """Fields submitted by the tutor when starting a new course pipeline run.

    Files must be uploaded first via POST /files. Pass the returned paths
    in `uploaded_file_paths`.
    """
    subject: str
    audience_age: str
    audience_level: str
    duration_weeks: int
    sessions_per_week: int
    sessions_total: int
    preferred_formats: list[str] = Field(
        description="e.g. ['lesson', 'video_script', 'quiz', 'worksheet']"
    )
    tone: str = Field(description="e.g. 'formal', 'casual', 'encouraging', 'socratic'")
    include_quiz: bool
    uploaded_file_paths: list[str] = Field(
        default=[],
        description="Absolute file paths returned by POST /files",
    )
    enrichment_urls: list[str] = []
    additional_context: str = ""


class ValidationResumeRequest(BaseModel):
    """Tutor verdict at HITL checkpoint #1 (validation feasibility report)."""
    approved: bool  # True → pipeline continues; False → routes to END


class CurriculumResumeRequest(BaseModel):
    """Tutor verdict at HITL checkpoint #2 (curriculum review)."""
    approved: bool
    retry_context: str = ""  # must be non-empty when approved=False


class CourseStatusResponse(BaseModel):
    """Standard response shape for all course pipeline endpoints.

    Status values:
    - queued                       task queued 
    - processing                   task processing
    - awaiting_validation          graph paused at HITL #1; data = interrupt payload
    - awaiting_curriculum_review   graph paused at HITL #2; data = interrupt payload
    - completed                    curriculum approved; data = curriculum_plan + session_content
    - rejected                     tutor declined at HITL #1; data = feasibility report
    - failed                       task failed
    """
    thread_id: str
    status: str
    data: dict


class CourseListItem(BaseModel):
    """Summary row returned by GET /users/{user_id}/courses."""
    thread_id: str
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime
    curriculum_plan: dict | None = None
    session_content: list | None = None


class CourseBriefResponse(BaseModel):
    """Original brief fields returned by GET /courses/{thread_id}/brief.

    Used to pre-populate the NewCourse form when a tutor wants to revise
    a rejected brief without starting from scratch.
    """
    subject: str
    audience_age: str
    audience_level: str
    duration_weeks: int
    sessions_per_week: int
    preferred_formats: list[str]
    tone: str
    additional_context: str
    enrichment_urls: list[str]
    uploaded_file_paths: list[str] = []  # S3 keys from the original upload
