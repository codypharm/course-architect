"""Curriculum and content planner node.

Three-phase approach that avoids LLM output-token limits on large courses:

  Phase 1 — ReAct research agent
      query_knowledge_base is called once per session topic to retrieve relevant
      knowledge-base chunks.  Produces a free-text research summary.

  Phase 2 — Outline synthesis  (one LLM call, all sessions)
      Produces CurriculumOutline: course_overview + per-session topic / objectives /
      lesson_outline.  Output is small (~500–2 000 tokens) regardless of session count.

  Phase 3 — Content generation  (one LLM call per session, parallelised)
      Each session gets its own call that generates only the format-specific content
      fields (lesson_content, video_script, quiz_questions, worksheet_exercises).
      Parallelising via asyncio.gather keeps wall-clock time low.



Retry support: when retry_context is set, all constraints are prepended as
HARD CONSTRAINT lines to every prompt in all three phases.

Returns:
    {
        "curriculum_plan": CurriculumPlan.model_dump(),
        "session_content": list[dict]  — one dict per session (SessionPlan.model_dump())
    }
"""
import asyncio
import json

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from tools.curriculum_planner import build_query_tool
from graph.state import CourseState
from schemas.curriculum import CurriculumOutline, CurriculumPlan, SessionPlan
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

# Phase 2: outline only — small output regardless of session count
_OUTLINE_PROMPT = """You are producing the structural outline for a {audience_level} course on {subject}.

Course parameters:
- Audience age: {audience_age}
- Duration: {duration_weeks} week(s), {sessions_per_week} session(s)/week ({sessions_total} sessions total)
- Tone: {tone}

Research notes:
{research_notes}

REQUIRED sessions — output one SessionOutline for every entry below, in order:
{session_slots}

Rules:
- Output exactly {sessions_total} SessionOutline objects — do NOT stop early
- Each session must have topic, 2–4 objectives, and 4–8 lesson_outline points
- Do NOT generate lesson_content, video_script, quiz_questions, or worksheet_exercises here
- Do NOT invent content not in the research notes
"""

# Phase 3: one call per session — generates format content only
_CONTENT_PROMPT = """{constraint_block}You are generating teaching content for one session of a {audience_level} course.

Subject: {subject}
Audience age: {audience_age}
Tone: {tone}
Session: Week {week}, Session {session} — {topic}

Learning objectives:
{objectives}

Lesson outline:
{lesson_outline}

Research notes for this topic:
{research_notes}

Format requirements for this course:
{format_populate}

Rules:
- week = {week}, session = {session}, topic = "{topic}" — copy these values verbatim into the output
- objectives and lesson_outline must match the values above exactly
- REQUIRED fields listed above must NOT be empty strings — generate full content per the JSON schema
- Tone guidance: {tone_guidance}
- Do NOT invent content not in the research notes
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
    """Return a REQUIRED/SKIP list for the per-session content prompt."""
    lines = []
    for fmt, field in _FORMAT_FIELD.items():
        if fmt in preferred_formats:
            lines.append(
                f"  REQUIRED — {field}: must NOT be empty — generate full content"
                f" exactly as described in the field's JSON schema description."
            )
        else:
            lines.append(f"  SKIP — {field}: leave as empty string / empty list (not selected)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_react_llm   = None
_outline_llm = None   # gpt-4o-mini — outline is structural, no heavy prose
_content_llm = None   # gpt-4o — per-session content, bound to SessionPlan schema
_outliner    = None
_content_gen = None


def _get_react_llm():
    """Lazily initialise the ReAct research LLM."""
    global _react_llm
    if _react_llm is None:
        _react_llm = init_chat_model(model="gpt-4o-mini", temperature=0.3)
    return _react_llm


def _get_outliner():
    """Lazily initialise the outline LLM (CurriculumOutline structured output)."""
    global _outline_llm, _outliner
    if _outline_llm is None:
        _outline_llm = init_chat_model(model="gpt-4o-mini", temperature=0.3)
        _outliner = _outline_llm.with_structured_output(CurriculumOutline)
    return _outliner


def _get_content_gen():
    """Lazily initialise the per-session content LLM (SessionPlan structured output).

    Uses gpt-4o so that prose fields (lesson_content, video_script) meet the
    400–700 word target without being truncated.
    """
    global _content_llm, _content_gen
    if _content_llm is None:
        _content_llm = init_chat_model(model="gpt-4o", temperature=0.3)
        _content_gen = _content_llm.with_structured_output(SessionPlan)
    return _content_gen


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------

def _build_constraint_block(state: CourseState) -> str:
    """Return a HARD CONSTRAINT block prepended to prompts on retry runs."""
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
    """LangGraph node. Three-phase curriculum planner.

    Phase 1: ReAct agent researches each session topic via the vector store.
    Phase 2: One structured call → CurriculumOutline (all sessions, outline only).
    Phase 3: One structured call per session → SessionPlan (format content only),
             parallelised via asyncio.gather to avoid sequential latency.

    Splitting Phase 2 from Phase 3 keeps each LLM response well within the
    16 384-token output limit even for an 18-session course.
    """
    subject: str          = state.get("subject", "")
    audience_age: str     = state.get("audience_age", "")
    audience_level: str   = state.get("audience_level", "")
    duration_weeks: int   = state.get("duration_weeks", 1)
    sessions_per_week: int = state.get("sessions_per_week", 1)
    sessions_total: int   = state.get("sessions_total", 1)
    preferred_formats: list[str] = state.get("preferred_formats", [])
    tone: str             = state.get("tone", "neutral")
    knowledge_summary: dict = state.get("knowledge_summary", {})
    retry_count: int      = state.get("retry_count", 0)

    logger.info(
        "Planning curriculum — subject: %s | sessions: %d | retry: %d",
        subject, sessions_total, retry_count,
    )

    constraint_block = _build_constraint_block(state)
    tone_guidance    = _TONE_GUIDANCE.get(tone, "Use a clear, accessible tone appropriate for the audience.")
    format_populate  = _build_format_populate(preferred_formats)

    # Explicit slot list so the LLM cannot stop early
    slot_lines = [
        f"  - Week {w}, Session {s}"
        for w in range(1, duration_weeks + 1)
        for s in range(1, sessions_per_week + 1)
    ]
    session_slots = "\n".join(slot_lines)

    # -----------------------------------------------------------------------
    # Phase 1 — ReAct research agent
    # -----------------------------------------------------------------------

    research_system = constraint_block + _RESEARCH_PROMPT.format(
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

    agent = create_react_agent(_get_react_llm(), [build_query_tool(state["thread_id"])])
    research_result = await agent.ainvoke({
        "messages": [
            SystemMessage(content=research_system),
            HumanMessage(content=_RESEARCH_HUMAN.format(sessions_total=sessions_total)),
        ]
    })

    final_ai_msgs = [
        m for m in research_result["messages"]
        if isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None)
    ]
    research_summary = final_ai_msgs[-1].content if final_ai_msgs else ""

    if not research_summary:
        logger.warning("ReAct agent produced no final summary — synthesis will rely on knowledge summary only")

    # -----------------------------------------------------------------------
    # Phase 2 — Outline synthesis (structural fields only, all sessions)
    # -----------------------------------------------------------------------

    outline_prompt = constraint_block + _OUTLINE_PROMPT.format(
        subject=subject,
        audience_age=audience_age,
        audience_level=audience_level,
        duration_weeks=duration_weeks,
        sessions_per_week=sessions_per_week,
        sessions_total=sessions_total,
        tone=tone,
        research_notes=research_summary,
        session_slots=session_slots,
    )

    outline: CurriculumOutline = await _get_outliner().ainvoke([
        HumanMessage(content=outline_prompt)
    ])

    logger.info(
        "Outline produced — %d/%d session(s)",
        len(outline.sessions), sessions_total,
    )
    if len(outline.sessions) < sessions_total:
        logger.warning(
            "Outliner returned fewer sessions than requested (%d vs %d)",
            len(outline.sessions), sessions_total,
        )

    # -----------------------------------------------------------------------
    # Phase 3 — Per-session content generation (parallelised)
    # -----------------------------------------------------------------------

    async def _generate_session_content(sess_outline) -> SessionPlan:
        """Generate format content for a single session."""
        objectives_text  = "\n".join(f"  - {o}" for o in sess_outline.objectives)
        outline_text     = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(sess_outline.lesson_outline))

        content_prompt = _CONTENT_PROMPT.format(
            constraint_block=constraint_block,
            subject=subject,
            audience_age=audience_age,
            audience_level=audience_level,
            tone=tone,
            week=sess_outline.week,
            session=sess_outline.session,
            topic=sess_outline.topic,
            objectives=objectives_text,
            lesson_outline=outline_text,
            research_notes=research_summary,
            format_populate=format_populate,
            tone_guidance=tone_guidance,
        )

        plan: SessionPlan = await _get_content_gen().ainvoke([
            HumanMessage(content=content_prompt)
        ])

        # Ensure structural fields match the outline (LLM may drift)
        plan.week    = sess_outline.week
        plan.session = sess_outline.session
        plan.topic   = sess_outline.topic
        if not plan.objectives:
            plan.objectives = sess_outline.objectives
        if not plan.lesson_outline:
            plan.lesson_outline = sess_outline.lesson_outline

        # Warn on any REQUIRED field that came back empty
        for fmt, field in _FORMAT_FIELD.items():
            if fmt not in preferred_formats:
                continue
            val = getattr(plan, field)
            if not val:
                logger.warning(
                    "Format field '%s' empty for W%d S%d despite '%s' selected",
                    field, plan.week, plan.session, fmt,
                )

        return plan

    session_plans: list[SessionPlan] = await asyncio.gather(
        *[_generate_session_content(s) for s in outline.sessions]
    )

    # Sort by (week, session) to guarantee order after parallel execution
    session_plans.sort(key=lambda s: (s.week, s.session))

    logger.info(
        "Content generation complete — %d session(s) | retry: %d",
        len(session_plans), retry_count,
    )

    # Assemble final CurriculumPlan using the outline's course_overview
    plan = CurriculumPlan(
        course_overview=outline.course_overview,
        sessions=session_plans,
    )

    session_content = [s.model_dump() for s in plan.sessions]

    return {
        "curriculum_plan": plan.model_dump(),
        "session_content": session_content,
    }
