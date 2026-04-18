"""Curriculum review HITL node (second interrupt checkpoint).

After the curriculum planner generates the full content plan, the pipeline pauses
here so the user can review it. The user either:
  - Approves  → sets curriculum_approved=True, graph routes to END (save)
  - Requests retry → sets retry_context + increments retry_count, graph loops
                     back to curriculum_planner where _build_constraint_block()
                     injects the context as a HARD CONSTRAINT into the prompt

Retry limit is enforced here: at 5 retries the node forces approval so the
pipeline cannot loop indefinitely.
"""
from datetime import datetime, timezone

from langgraph.types import interrupt

from graph.state import CourseState
from utils.logging import get_logger

logger = get_logger(__name__)

_MAX_RETRIES = 5


async def curriculum_review_node(state: CourseState) -> dict:
    """LangGraph node. Pauses for user review of the curriculum plan.

    Sends curriculum_plan and session_content to the UI via interrupt().
    Resumes when the user submits a verdict dict:
        {"approved": bool, "retry_context": str}  # retry_context required only when not approved
    """
    retry_count: int = state.get("retry_count", 0)

    logger.info(
        "Awaiting curriculum review — retry %d/%d",
        retry_count, _MAX_RETRIES,
    )

    verdict = interrupt({
        "curriculum_plan": state.get("curriculum_plan", {}),
        "session_content": state.get("session_content", []),
        "retry_count": retry_count,
        "max_retries": _MAX_RETRIES,
    })

    if verdict["approved"]:
        logger.info("Curriculum approved by user")
        return {
            "curriculum_approved": True,
            "curriculum_feedback": "",
        }

    # Retry requested
    retry_context: str = verdict.get("retry_context", "").strip()

    if retry_count >= _MAX_RETRIES:
        logger.warning(
            "Retry limit (%d) reached — forcing curriculum approval",
            _MAX_RETRIES,
        )
        return {
            "curriculum_approved": True,
            "curriculum_feedback": retry_context,
        }

    new_count = retry_count + 1
    timestamp = datetime.now(timezone.utc).isoformat()

    updated_history = [
        *state.get("retry_history", []),
        {"retry_count": new_count, "retry_context": retry_context, "timestamp": timestamp},
    ]

    logger.info(
        "Retry %d requested — context: %.80s",
        new_count, retry_context,
    )

    return {
        "curriculum_approved": False,
        "curriculum_feedback": retry_context,
        "retry_context": retry_context,     # picked up by _build_constraint_block() in curriculum_planner
        "retry_count": new_count,
        "retry_history": updated_history,
    }
