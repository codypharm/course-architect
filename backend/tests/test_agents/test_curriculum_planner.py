import pytest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from agents.curriculum_planner import curriculum_planner_agent
from schemas.curriculum import CurriculumPlan, QuizQuestion, SessionPlan

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_STATE = {
    "subject": "Python Programming",
    "audience_age": "16-18 years",
    "audience_level": "beginner",
    "duration_weeks": 2,
    "sessions_per_week": 2,
    "sessions_total": 4,
    "preferred_formats": ["lesson", "quiz"],
    "tone": "encouraging",
    "include_quiz": True,
    "knowledge_summary": {
        "content_overview": "Covers variables, loops, functions.",
        "total_topics": ["variables", "loops", "functions"],
        "coverage_depth": "introductory",
        "total_teaching_minutes": 120,
        "prerequisites": ["basic computer literacy"],
        "gaps": [],
        "fit_for_audience": "Good fit.",
        "fit_for_duration": "Good fit.",
        "recommendations": [],
    },
    "retry_count": 0,
    "retry_context": "",
    "retry_history": [],
}

_QUIZ = [
    QuizQuestion(
        question="What does `print()` do?",
        options=["Displays output", "Reads input", "Stores a value", "Imports a module"],
        answer="Displays output",
        explanation="print() outputs text to the console.",
    )
]

SAMPLE_PLAN = CurriculumPlan(
    course_overview="A 2-week beginner Python course covering variables, loops, and functions.",
    sessions=[
        SessionPlan(week=1, session=1, topic="Variables and Data Types",
                    objectives=["Define variables", "Use basic types"],
                    lesson_outline=["What is a variable?", "int vs str", "Assignment syntax"],
                    quiz_questions=_QUIZ),
        SessionPlan(week=1, session=2, topic="Control Flow",
                    objectives=["Write if statements"],
                    lesson_outline=["Boolean conditions", "if/elif/else"],
                    quiz_questions=_QUIZ),
        SessionPlan(week=2, session=1, topic="Loops",
                    objectives=["Write for and while loops"],
                    lesson_outline=["for loop syntax", "while loop syntax", "break/continue"],
                    quiz_questions=_QUIZ),
        SessionPlan(week=2, session=2, topic="Functions",
                    objectives=["Define and call functions"],
                    lesson_outline=["def keyword", "Parameters and return values"],
                    quiz_questions=_QUIZ),
    ],
)

SAMPLE_PLAN_NO_QUIZ = CurriculumPlan(
    course_overview="A 2-week beginner Python course.",
    sessions=[
        SessionPlan(week=1, session=1, topic="Variables",
                    objectives=["Define variables"],
                    lesson_outline=["What is a variable?"],
                    quiz_questions=[]),
        SessionPlan(week=1, session=2, topic="Control Flow",
                    objectives=["Write if statements"],
                    lesson_outline=["if/elif/else"],
                    quiz_questions=[]),
        SessionPlan(week=2, session=1, topic="Loops",
                    objectives=["Write loops"],
                    lesson_outline=["for loop"],
                    quiz_questions=[]),
        SessionPlan(week=2, session=2, topic="Functions",
                    objectives=["Define functions"],
                    lesson_outline=["def keyword"],
                    quiz_questions=[]),
    ],
)


def _make_agent_result(summary: str = "Research notes: variables → assignment; loops → iteration.") -> dict:
    """Build a mock ReAct agent result with tool calls followed by a final summary."""
    return {
        "messages": [
            HumanMessage(content="Research all sessions."),
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "query_knowledge_base", "args": {"query": "Python variables"}}]),
            AIMessage(content="", tool_calls=[{"id": "c2", "name": "query_knowledge_base", "args": {"query": "Python loops"}}]),
            AIMessage(content=summary),
        ]
    }


def _apply_patches(stack: ExitStack, mock_agent, mock_planner):
    """Enter all standard curriculum_planner patches into an ExitStack."""
    stack.enter_context(patch("agents.curriculum_planner.create_react_agent", return_value=mock_agent))
    stack.enter_context(patch("agents.curriculum_planner._get_planner", return_value=mock_planner))
    stack.enter_context(patch("agents.curriculum_planner._get_react_llm"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_returns_curriculum_plan_and_session_content():
    """Both output keys present and session_content has lesson_outline + quiz_questions."""
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result()
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with ExitStack() as stack:
        _apply_patches(stack, mock_agent, mock_planner)
        result = await curriculum_planner_agent(MINIMAL_STATE)

    assert "curriculum_plan" in result
    assert "session_content" in result
    assert len(result["session_content"]) == 4
    s = result["session_content"][0]
    assert "lesson_outline" in s
    assert "quiz_questions" in s
    assert isinstance(s["lesson_outline"], list)
    assert isinstance(s["quiz_questions"], list)


@pytest.mark.anyio
async def test_react_agent_called_once():
    """create_react_agent is used and the returned agent is invoked exactly once."""
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result()
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with patch("agents.curriculum_planner.create_react_agent", return_value=mock_agent) as mock_create, \
         patch("agents.curriculum_planner._get_planner", return_value=mock_planner), \
         patch("agents.curriculum_planner._get_react_llm"):
        await curriculum_planner_agent(MINIMAL_STATE)

    mock_create.assert_called_once()
    mock_agent.ainvoke.assert_called_once()


@pytest.mark.anyio
async def test_synthesis_uses_agent_final_message():
    """The planner's ainvoke call receives the agent's final summary text."""
    summary_text = "Session 1: variables — assignment and types. Session 2: loops — iteration."
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result(summary=summary_text)
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with ExitStack() as stack:
        _apply_patches(stack, mock_agent, mock_planner)
        await curriculum_planner_agent(MINIMAL_STATE)

    call_messages = mock_planner.ainvoke.call_args[0][0]
    assert any(summary_text in msg.content for msg in call_messages)


@pytest.mark.anyio
async def test_retry_context_injected_into_system_prompt():
    """retry_context appears verbatim as HARD CONSTRAINT in the ReAct system message."""
    state = {
        **MINIMAL_STATE,
        "retry_context": "Focus more on practical code examples",
        "retry_count": 1,
        "retry_history": [],
    }
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result()
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with ExitStack() as stack:
        _apply_patches(stack, mock_agent, mock_planner)
        await curriculum_planner_agent(state)

    messages = mock_agent.ainvoke.call_args[0][0]["messages"]
    system_content = messages[0].content
    assert "HARD CONSTRAINT: Focus more on practical code examples" in system_content


@pytest.mark.anyio
async def test_all_retry_history_constraints_included_on_retry_3():
    """On retry 3+, all prior history entries plus the current constraint appear."""
    state = {
        **MINIMAL_STATE,
        "retry_count": 3,
        "retry_context": "Add more real-world examples",
        "retry_history": [
            {"retry_count": 1, "retry_context": "Focus on practical code", "timestamp": "2026-01-01"},
            {"retry_count": 2, "retry_context": "Reduce theory, add exercises", "timestamp": "2026-01-02"},
        ],
    }
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result()
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with ExitStack() as stack:
        _apply_patches(stack, mock_agent, mock_planner)
        await curriculum_planner_agent(state)

    system_content = mock_agent.ainvoke.call_args[0][0]["messages"][0].content
    assert "HARD CONSTRAINT: Focus on practical code" in system_content
    assert "HARD CONSTRAINT: Reduce theory, add exercises" in system_content
    assert "HARD CONSTRAINT: Add more real-world examples" in system_content


@pytest.mark.anyio
async def test_no_retry_constraint_when_retry_context_empty():
    """HARD CONSTRAINT must not appear when retry_context is empty."""
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result()
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with ExitStack() as stack:
        _apply_patches(stack, mock_agent, mock_planner)
        await curriculum_planner_agent(MINIMAL_STATE)

    system_content = mock_agent.ainvoke.call_args[0][0]["messages"][0].content
    assert "HARD CONSTRAINT" not in system_content


@pytest.mark.anyio
async def test_quiz_questions_empty_when_quiz_not_in_formats():
    """When 'quiz' is absent from preferred_formats, all session_content items have empty quiz_questions."""
    state = {**MINIMAL_STATE, "preferred_formats": ["lesson"], "include_quiz": False}
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result()
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN_NO_QUIZ

    with ExitStack() as stack:
        _apply_patches(stack, mock_agent, mock_planner)
        result = await curriculum_planner_agent(state)

    for s in result["session_content"]:
        assert s["quiz_questions"] == []


@pytest.mark.anyio
async def test_handles_empty_agent_summary():
    """When the ReAct agent produces no final summary, synthesis still runs with empty research_notes."""
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {
        "messages": [
            HumanMessage(content="Research all sessions."),
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "query_knowledge_base", "args": {}}]),
        ]
    }
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with ExitStack() as stack:
        _apply_patches(stack, mock_agent, mock_planner)
        result = await curriculum_planner_agent(MINIMAL_STATE)

    assert "curriculum_plan" in result
    # Synthesis was still called
    mock_planner.ainvoke.assert_called_once()


@pytest.mark.anyio
async def test_curriculum_plan_serialised_to_dict():
    """curriculum_plan and session_content entries must be plain dicts, not Pydantic models."""
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result()
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with ExitStack() as stack:
        _apply_patches(stack, mock_agent, mock_planner)
        result = await curriculum_planner_agent(MINIMAL_STATE)

    assert isinstance(result["curriculum_plan"], dict)
    assert isinstance(result["session_content"], list)
    assert isinstance(result["session_content"][0], dict)
    assert isinstance(result["session_content"][0]["quiz_questions"][0], dict)
