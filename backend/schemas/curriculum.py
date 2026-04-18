from pydantic import BaseModel


class SessionPlan(BaseModel):
    """Plan for a single teaching session."""
    week: int
    session: int          # session number within the week (1-based)
    topic: str
    objectives: list[str]  # learning objectives for this session


class CurriculumPlan(BaseModel):
    """Full course curriculum produced by the curriculum planner."""
    course_overview: str        # one paragraph covering the arc of the whole course
    sessions: list[SessionPlan]
