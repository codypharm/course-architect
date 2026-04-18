import pytest
from unittest.mock import AsyncMock, patch

from agents.curriculum_planner import curriculum_planner_agent
from schemas.curriculum import CurriculumPlan, SessionPlan

MINIMAL_STATE = {
    "subject": "Python Programming",
    "audience_age": "16-18 years",
    "audience_level": "beginner",
    "duration_weeks": 2,
    "sessions_per_week": 2,
    "sessions_total": 4,
    "preferred_formats": ["lesson", "quiz"],
    "tone": "encouraging",
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
}

SAMPLE_PLAN = CurriculumPlan(
    course_overview="A beginner Python course covering variables, loops, and functions over 2 weeks.",
    sessions=[
        SessionPlan(week=1, session=1, topic="Variables and Data Types", objectives=["Define variables", "Use basic types"]),
        SessionPlan(week=1, session=2, topic="Control Flow", objectives=["Write if statements", "Use comparison operators"]),
        SessionPlan(week=2, session=1, topic="Loops", objectives=["Write for loops", "Write while loops"]),
        SessionPlan(week=2, session=2, topic="Functions", objectives=["Define functions", "Return values"]),
    ],
)


@pytest.mark.anyio
async def test_returns_curriculum_plan():
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with patch("agents.curriculum_planner._get_planner", return_value=mock_planner), \
         patch("agents.curriculum_planner.retrieve", return_value="Relevant KB content here."):
        result = await curriculum_planner_agent(MINIMAL_STATE)

    assert "curriculum_plan" in result
    plan = result["curriculum_plan"]
    assert len(plan["sessions"]) == 4
    assert plan["sessions"][0]["week"] == 1
    assert plan["sessions"][0]["topic"] == "Variables and Data Types"
    assert "course_overview" in plan


@pytest.mark.anyio
async def test_calls_retrieve_with_subject_context():
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with patch("agents.curriculum_planner._get_planner", return_value=mock_planner), \
         patch("agents.curriculum_planner.retrieve", return_value="KB content") as mock_retrieve:
        await curriculum_planner_agent(MINIMAL_STATE)

    mock_retrieve.assert_called_once()
    query_arg = mock_retrieve.call_args[1]["query"] if mock_retrieve.call_args[1] else mock_retrieve.call_args[0][0]
    assert "Python Programming" in query_arg


@pytest.mark.anyio
async def test_handles_empty_vector_store():
    """Node should proceed gracefully when vector store returns no content."""
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with patch("agents.curriculum_planner._get_planner", return_value=mock_planner), \
         patch("agents.curriculum_planner.retrieve", return_value=""):
        result = await curriculum_planner_agent(MINIMAL_STATE)

    # Should still produce a plan — LLM falls back to priors
    assert "curriculum_plan" in result


@pytest.mark.anyio
async def test_plan_serialised_to_dict():
    """curriculum_plan in state must be a plain dict, not a Pydantic model."""
    mock_planner = AsyncMock()
    mock_planner.ainvoke.return_value = SAMPLE_PLAN

    with patch("agents.curriculum_planner._get_planner", return_value=mock_planner), \
         patch("agents.curriculum_planner.retrieve", return_value="KB content"):
        result = await curriculum_planner_agent(MINIMAL_STATE)

    assert isinstance(result["curriculum_plan"], dict)
    assert isinstance(result["curriculum_plan"]["sessions"], list)
    assert isinstance(result["curriculum_plan"]["sessions"][0], dict)
