"""ORM models for persistent course storage.

CourseRecord is the single table tracking every course generation run.
It is written at course start and updated on each HITL status transition.
The full curriculum is persisted only when the user approves at HITL #2.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from storage.database import Base


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class CourseRecord(Base):
    """One row per course pipeline run."""

    __tablename__ = "courses"

    # Identifiers
    id: Mapped[str] = mapped_column(String, primary_key=True)        # UUID
    thread_id: Mapped[str] = mapped_column(String, unique=True)      # LangGraph thread
    user_id: Mapped[str] = mapped_column(String)                     # Clerk user_id (unverified in Phase 1)

    # Course metadata
    subject: Mapped[str] = mapped_column(String)

    # Pipeline status — one of:
    # "awaiting_validation" | "awaiting_curriculum_review" | "completed" | "rejected"
    status: Mapped[str] = mapped_column(String)

    # Final output — null until the user approves at HITL #2
    curriculum_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    session_content: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_courses_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<CourseRecord id={self.id!r} subject={self.subject!r} status={self.status!r}>"
