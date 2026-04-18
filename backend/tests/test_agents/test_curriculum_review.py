import pytest
from unittest.mock import patch

from agents.curriculum_review import curriculum_review_node

SAMPLE_PLAN = {"course_overview": "Python basics.", "sessions": []}
SAMPLE_CONTENT = [{"week": 1, "session": 1, "topic": "Variables", "lesson_outline": [], "quiz_questions": []}]

MINIMAL_STATE = {
    "curriculum_plan": SAMPLE_PLAN,
    "session_content": SAMPLE_CONTENT,
    "retry_count": 0,
    "retry_context": "",
    "retry_history": [],
}


@pytest.mark.anyio
async def test_approval_sets_curriculum_approved_true():
    """Approved verdict returns curriculum_approved=True and clears feedback."""
    with patch("agents.curriculum_review.interrupt", return_value={"approved": True}):
        result = await curriculum_review_node(MINIMAL_STATE)

    assert result["curriculum_approved"] is True
    assert result["curriculum_feedback"] == ""


@pytest.mark.anyio
async def test_retry_sets_retry_fields():
    """Retry verdict sets retry_context, increments retry_count, appends to retry_history."""
    verdict = {"approved": False, "retry_context": "Make week 2 more practical"}
    with patch("agents.curriculum_review.interrupt", return_value=verdict):
        result = await curriculum_review_node(MINIMAL_STATE)

    assert result["curriculum_approved"] is False
    assert result["retry_context"] == "Make week 2 more practical"
    assert result["curriculum_feedback"] == "Make week 2 more practical"
    assert result["retry_count"] == 1
    assert len(result["retry_history"]) == 1
    assert result["retry_history"][0]["retry_context"] == "Make week 2 more practical"
    assert result["retry_history"][0]["retry_count"] == 1


@pytest.mark.anyio
async def test_retry_limit_forces_approval():
    """At retry_count == 5, forces curriculum_approved=True regardless of verdict."""
    state = {**MINIMAL_STATE, "retry_count": 5}
    verdict = {"approved": False, "retry_context": "Still not happy"}
    with patch("agents.curriculum_review.interrupt", return_value=verdict):
        result = await curriculum_review_node(state)

    assert result["curriculum_approved"] is True


@pytest.mark.anyio
async def test_retry_history_accumulates():
    """Existing retry_history entries are preserved and the new entry is appended."""
    state = {
        **MINIMAL_STATE,
        "retry_count": 2,
        "retry_history": [
            {"retry_count": 1, "retry_context": "Add examples", "timestamp": "2026-01-01T00:00:00+00:00"},
            {"retry_count": 2, "retry_context": "Shorten sessions", "timestamp": "2026-01-02T00:00:00+00:00"},
        ],
    }
    verdict = {"approved": False, "retry_context": "Focus on beginners"}
    with patch("agents.curriculum_review.interrupt", return_value=verdict):
        result = await curriculum_review_node(state)

    assert len(result["retry_history"]) == 3
    assert result["retry_history"][0]["retry_context"] == "Add examples"
    assert result["retry_history"][2]["retry_context"] == "Focus on beginners"


@pytest.mark.anyio
async def test_interrupt_receives_plan_and_content():
    """interrupt() is called with curriculum_plan and session_content from state."""
    with patch("agents.curriculum_review.interrupt", return_value={"approved": True}) as mock_interrupt:
        await curriculum_review_node(MINIMAL_STATE)

    payload = mock_interrupt.call_args[0][0]
    assert payload["curriculum_plan"] == SAMPLE_PLAN
    assert payload["session_content"] == SAMPLE_CONTENT
    assert "retry_count" in payload
    assert "max_retries" in payload
