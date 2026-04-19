"""Curriculum and content planner node.

Two-phase approach mirroring gap_enrichment.py:
  1. ReAct agent with a query_knowledge_base tool researches each session topic
     by calling the vector store as many times as it needs.
  2. A structured LLM call synthesises the research notes into a full CurriculumPlan
     (lesson outlines + quiz questions per session).

Retry support: when retry_context is set in state, all constraints are prepended
to the system prompt verbatim as HARD CONSTRAINT lines. Prior retry_history entries
are also included on retry 3+.

Returns:
    {
        "curriculum_plan": CurriculumPlan.model_dump(),
        "session_content": list[dict]  — per-session lesson + quiz content
    }
"""
import json

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from tools.curriculum_planner import query_knowledge_base
from graph.state import CourseState
from schemas.curriculum import CurriculumPlan
from utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_RESEARCH_PROMPT = """You are an expert curriculum researcher preparing material for a {audience_level} course.

Course parameters:
- Subject: {subject}
- Audience age: {audience_age}
- Audience level: {audience_level}
- Duration: {duration_weeks} week(s), {sessions_per_week} session(s)/week ({sessions_total} sessions total)
- Preferred formats: {preferred_formats}
- Tone: {tone}

Knowledge base summary:
{knowledge_summary}

Your task: research teaching material for each of the {sessions_total} sessions.

For each session topic (distribute the subject across {sessions_total} sessions logically):
1. Call query_knowledge_base with a targeted query for that topic
2. Note the key concepts, definitions, and teaching points retrieved

When finished, write a structured research summary — one section per session — listing:
- Proposed topic
- Key teaching points found in the knowledge base
- Suggested quiz angle (even if quiz will not be generated)

Ground every session in what you actually retrieved. Do not invent content not in the knowledge base.
"""

_RESEARCH_HUMAN = "Research all {sessions_total} sessions now. Call query_knowledge_base once per topic."

_SYNTHESIS_PROMPT = """You are producing a full course curriculum and content plan.

Course parameters:
- Subject: {subject}
- Audience age: {audience_age}
- Audience level: {audience_level}
- Duration: {duration_weeks} week(s), {sessions_per_week} session(s)/week ({sessions_total} sessions total)
- Tone: {tone}

Formats selected by the tutor (populate these fields per session; leave all others empty):
{format_populate}

Knowledge base summary:
{knowledge_summary}

Research notes (retrieved knowledge base content per session):
{research_notes}

REQUIRED sessions — output one SessionPlan for every entry below, in order:
{session_slots}

Rules:
- Output exactly {sessions_total} sessions — do NOT stop early, do NOT skip any
- lesson_outline and objectives are always populated for every session
- Every format field has its generation spec in the JSON schema description — follow it exactly
- Tone: {tone_guidance}
- Do NOT invent content not present in the research notes or knowledge base summary
"""

_TONE_GUIDANCE = {
    "formal":      "Use precise academic language. Avoid colloquialisms.",
    "casual":      "Use friendly, conversational language. Short sentences.",
    "encouraging": "Use positive framing. Celebrate small wins. Motivate learners.",
    "socratic":    "Frame teaching points as questions that lead students to discover answers.",
}

# Maps format id → the SessionPlan field name it populates
_FORMAT_FIELD = {
    "lesson":       "lesson_content",
    "video_script": "video_script",
    "quiz":         "quiz_questions",
    "worksheet":    "worksheet_exercises",
}


def _build_format_populate(preferred_formats: list[str]) -> str:
    """Return a short populate/skip list so the model knows which fields to fill.

    Full generation specs live in the Pydantic Field descriptions on SessionPlan
    and are passed to the model automatically via the JSON schema.
    """
    lines = []
    for fmt, field in _FORMAT_FIELD.items():
        if fmt in preferred_formats:
            lines.append(f"  ✓ populate  {field}")
        else:
            lines.append(f"  ✗ leave empty  {field}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Lazy singletons — two separate model instances to avoid binding conflicts
# ---------------------------------------------------------------------------

_react_llm = None
_synthesizer_llm = None
_planner = None


def _get_react_llm():
    """Lazily initialise the LLM used by the ReAct agent (unbound)."""
    global _react_llm
    if _react_llm is None:
        _react_llm = init_chat_model(model="gpt-4o-mini", temperature=0.3)
    return _react_llm


def _get_planner():
    """Lazily initialise the structured-output LLM used for synthesis.

    Uses gpt-4o rather than gpt-4o-mini: the full CurriculumPlan for a multi-week
    course (sessions × objectives + lesson points + quiz questions) can exceed
    gpt-4o-mini's output token budget, causing silent truncation of later weeks.
    """
    global _synthesizer_llm, _planner
    if _synthesizer_llm is None:
        _synthesizer_llm = init_chat_model(model="gpt-4o", temperature=0.3)
        _planner = _synthesizer_llm.with_structured_output(CurriculumPlan)
    return _planner


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------

def _build_constraint_block(state: CourseState) -> str:
    """Return a HARD CONSTRAINT block prepended to the system prompt on retry runs.

    On retry 3+ all prior history entries are included so the agent honours
    every accumulated constraint, not just the latest one.
    """
    retry_context: str = state.get("retry_context", "")
    retry_history: list[dict] = state.get("retry_history", [])
    if not retry_context:
        return ""
    lines = []
    for entry in retry_history:
        prior = entry.get("retry_context", "")
        if prior and prior != retry_context:
            lines.append(f"HARD CONSTRAINT: {prior}")
    lines.append(f"HARD CONSTRAINT: {retry_context}")
    return "\n".join(lines) + "\n\n"


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def curriculum_planner_agent(state: CourseState) -> dict:
    """LangGraph node. Researches each session topic via the vector store, then
    synthesises a full CurriculumPlan with lesson outlines and quiz questions.

    Phase 1: ReAct agent calls query_knowledge_base once per topic.
    Phase 2: Structured LLM call produces CurriculumPlan from research notes.
    """
    subject: str = state.get("subject", "")
    audience_age: str = state.get("audience_age", "")
    audience_level: str = state.get("audience_level", "")
    duration_weeks: int = state.get("duration_weeks", 1)
    sessions_per_week: int = state.get("sessions_per_week", 1)
    sessions_total: int = state.get("sessions_total", 1)
    preferred_formats: list[str] = state.get("preferred_formats", [])
    tone: str = state.get("tone", "neutral")
    include_quiz: bool = state.get("include_quiz", False)
    knowledge_summary: dict = state.get("knowledge_summary", {})
    retry_count: int = state.get("retry_count", 0)

    logger.info(
        "Planning curriculum — subject: %s | sessions: %d | retry: %d",
        subject, sessions_total, retry_count,
    )

    # --- Phase 1: ReAct research agent ---

    constraint_block = _build_constraint_block(state)
    system_content = constraint_block + _RESEARCH_PROMPT.format(
        subject=subject,
        audience_age=audience_age,
        audience_level=audience_level,
        duration_weeks=duration_weeks,
        sessions_per_week=sessions_per_week,
        sessions_total=sessions_total,
        preferred_formats=", ".join(preferred_formats) if preferred_formats else "none specified",
        tone=tone,
        knowledge_summary=json.dumps(knowledge_summary, indent=2),
    )

    agent = create_react_agent(_get_react_llm(), [query_knowledge_base])
    research_result = await agent.ainvoke({
        "messages": [
            SystemMessage(content=system_content),
            HumanMessage(content=_RESEARCH_HUMAN.format(sessions_total=sessions_total)),
        ]
    })

    # Extract the agent's final summary message (non-tool-call AIMessage)
    final_ai_messages = [
        m for m in research_result["messages"]
        if isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None)
    ]
    research_summary = final_ai_messages[-1].content if final_ai_messages else ""

    if not research_summary:
        logger.warning("ReAct agent produced no final summary — synthesis will rely on knowledge summary only")

    # --- Phase 2: Structured synthesis ---

    tone_guidance = _TONE_GUIDANCE.get(tone, "Use a clear, accessible tone appropriate for the audience.")

    # Explicit slot list so the LLM cannot stop early
    slot_lines = [
        f"  - Week {w}, Session {s}"
        for w in range(1, duration_weeks + 1)
        for s in range(1, sessions_per_week + 1)
    ]
    session_slots = "\n".join(slot_lines)

    synthesis_content = _SYNTHESIS_PROMPT.format(
        subject=subject,
        audience_age=audience_age,
        audience_level=audience_level,
        duration_weeks=duration_weeks,
        sessions_per_week=sessions_per_week,
        sessions_total=sessions_total,
        tone=tone,
        knowledge_summary=json.dumps(knowledge_summary, indent=2),
        research_notes=research_summary,
        tone_guidance=tone_guidance,
        session_slots=session_slots,
        format_populate=_build_format_populate(preferred_formats),
    )

    plan: CurriculumPlan = await _get_planner().ainvoke([
        HumanMessage(content=synthesis_content)
    ])

    logger.info(
        "Curriculum plan produced — %d/%d session(s), retry: %d",
        len(plan.sessions), sessions_total, retry_count,
    )
    if len(plan.sessions) < sessions_total:
        logger.warning(
            "LLM returned fewer sessions than requested (%d vs %d) — consider retrying",
            len(plan.sessions), sessions_total,
        )

    # session_content carries all format fields; empty fields are omitted from the dict
    # when they were not requested so the UI can gate display on presence.
    session_content = [s.model_dump() for s in plan.sessions]

    return {
        "curriculum_plan": plan.model_dump(),
        "session_content": session_content,
    }
