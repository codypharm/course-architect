"""Curriculum planner node.

Generates a session-by-session curriculum plan from the approved CourseState.
Retrieves relevant chunks from the vector store so the plan is grounded in the
actual knowledge base rather than the LLM's priors.

Returns:
    {"curriculum_plan": CurriculumPlan.model_dump()}
"""
import json

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import CourseState
from rag.retrieval import retrieve
from schemas.curriculum import CurriculumPlan
from utils.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are an expert curriculum designer for {audience_level} learners aged {audience_age}.

Your task is to produce a detailed session-by-session course plan.

Course parameters:
- Subject: {subject}
- Duration: {duration_weeks} week(s), {sessions_per_week} session(s) per week ({sessions_total} sessions total)
- Audience age: {audience_age}
- Audience level: {audience_level}
- Preferred formats: {preferred_formats}
- Tone: {tone}

Knowledge base summary:
{knowledge_summary}

Relevant knowledge base content (use this to ground each session in real material):
{rag_context}

Instructions:
- Cover all {sessions_total} sessions — do not skip any
- Distribute topics logically: foundational topics early, advanced topics later
- Each session must have 2–4 specific, measurable learning objectives
- Topics must match the audience age and level — no jargon without explanation for young audiences
- Do not invent topics not supported by the knowledge base unless absolutely necessary to fill the schedule
- Write a course_overview paragraph that summarises the arc of the full course
"""

_HUMAN_PROMPT = "Generate the full curriculum plan for all {sessions_total} sessions."

_llm = None
_planner = None


def _get_planner():
    """Lazily initialise the structured output LLM for curriculum planning."""
    global _llm, _planner
    if _llm is None:
        _llm = init_chat_model(model="gpt-4o-mini", temperature=0.3)
        _planner = _llm.with_structured_output(CurriculumPlan)
    return _planner


async def curriculum_planner_agent(state: CourseState) -> dict:
    """LangGraph node. Generates a full session-by-session curriculum plan.

    Retrieves knowledge base chunks relevant to the course subject, then uses
    a structured LLM call to produce a CurriculumPlan covering every session.
    """
    subject: str = state.get("subject", "")
    audience_age: str = state.get("audience_age", "")
    audience_level: str = state.get("audience_level", "")
    duration_weeks: int = state.get("duration_weeks", 1)
    sessions_per_week: int = state.get("sessions_per_week", 1)
    sessions_total: int = state.get("sessions_total", 1)
    preferred_formats: list[str] = state.get("preferred_formats", [])
    tone: str = state.get("tone", "neutral")
    knowledge_summary: dict = state.get("knowledge_summary", {})

    logger.info(
        "Planning curriculum — subject: %s | sessions: %d | audience: %s %s",
        subject, sessions_total, audience_age, audience_level,
    )

    # Retrieve knowledge base content to ground the plan in real material
    rag_context = retrieve(
        query=f"{subject} curriculum topics for {audience_level} learners aged {audience_age}",
        k=10,
    )
    if not rag_context:
        logger.warning("Vector store returned no chunks — plan will rely on LLM priors")
        rag_context = "No knowledge base content available."

    planner = _get_planner()
    system_content = _SYSTEM_PROMPT.format(
        subject=subject,
        audience_age=audience_age,
        audience_level=audience_level,
        duration_weeks=duration_weeks,
        sessions_per_week=sessions_per_week,
        sessions_total=sessions_total,
        preferred_formats=", ".join(preferred_formats) if preferred_formats else "none specified",
        tone=tone,
        knowledge_summary=json.dumps(knowledge_summary, indent=2),
        rag_context=rag_context,
    )

    plan: CurriculumPlan = await planner.ainvoke([
        SystemMessage(content=system_content),
        HumanMessage(content=_HUMAN_PROMPT.format(sessions_total=sessions_total)),
    ])

    logger.info(
        "Curriculum plan produced — %d session(s) across %d week(s)",
        len(plan.sessions), duration_weeks,
    )

    return {"curriculum_plan": plan.model_dump()}
