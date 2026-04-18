"""Shared LangGraph helpers used by both the API layer and Celery tasks."""


def graph_config(thread_id: str) -> dict:
    """Build the LangGraph config dict for a given thread."""
    return {"configurable": {"thread_id": thread_id}}


def derive_pipeline_status(values: dict, paused_at: tuple) -> tuple[str, dict]:
    """Return (status, data) from a graph snapshot.

    `paused_at` is LangGraph's state.next — the node(s) currently frozen mid-execution
    by interrupt(). When a node calls interrupt(), it re-appears here because it still
    needs to finish once the client resumes. Falls back to state field values when the
    graph has completed (paused_at is empty).
    """
    paused_set = set(paused_at)

    if "validation" in paused_set:
        return "awaiting_validation", {
            "feasibility_report": values.get("feasibility_report", {}),
            "flags": values.get("flags", []),
            "suggestions": values.get("suggestions", []),
            "estimated_cost_usd": values.get("estimated_cost_usd", 0.0),
        }

    if "curriculum_review" in paused_set:
        return "awaiting_curriculum_review", {
            "curriculum_plan": values.get("curriculum_plan", {}),
            "session_content": values.get("session_content", []),
            "retry_count": values.get("retry_count", 0),
        }

    if values.get("curriculum_approved"):
        return "completed", {
            "curriculum_plan": values.get("curriculum_plan", {}),
            "session_content": values.get("session_content", []),
        }

    return "rejected", {
        "feasibility_report": values.get("feasibility_report", {}),
        "flags": values.get("flags", []),
        "suggestions": values.get("suggestions", []),
    }
