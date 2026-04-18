from pydantic import BaseModel


class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question."""
    question: str
    options: list[str]   # exactly 4 MCQ options
    answer: str          # must match one of the options verbatim
    explanation: str     # why this answer is correct


class SessionPlan(BaseModel):
    """Full content plan for one teaching session."""
    week: int
    session: int          # session number within the week (1-based)
    topic: str
    objectives: list[str]           # measurable learning objectives
    lesson_outline: list[str]       # ordered key teaching points
    quiz_questions: list[QuizQuestion]  # 2-4 questions; empty if quiz not in preferred_formats


class CurriculumPlan(BaseModel):
    """Complete course curriculum and content plan."""
    course_overview: str    # one paragraph covering the arc of the full course
    sessions: list[SessionPlan]
