"""Shared LangGraph helpers used by both the API layer and Celery tasks."""


def infer_processing_stage(values: dict) -> int:
    """Infer which pipeline stage is currently active from the last saved checkpoint.

    LangGraph checkpoints state at node *completion*, so snapshot.values reflects
    the end of the most recently finished node.  We use the presence of key fields
    to deduce how far the pipeline has progressed:

      0 — submitted / queued
      1 — validating feasibility      (preprocessor ran, no feasibility_report yet)
      2 — enriching knowledge base    (validation passed, gap enrichment running)
      3 — generating curriculum       (enrichment done, curriculum planner running)
      4 — finalising                  (curriculum plan exists, content saving)

    Returns an int in [0, 4].
    """
    if values.get("curriculum_plan") or values.get("session_content"):
        return 4

    if values.get("knowledge_summary"):
        ks = values["knowledge_summary"]
        # gaps == [] means enrichment finished → curriculum planner is now running
        if isinstance(ks, dict) and not ks.get("gaps"):
            return 3
        # knowledge_summary present but gaps still listed → enrichment running
        return 2

    if values.get("feasibility_report"):
        # validation done, enrichment not yet started
        return 2

    return 1


def graph_config(thread_id: str) -> dict:
    """Build the LangGraph config dict for a given thread."""
    return {"configurable": {"thread_id": thread_id}}


def _read_interrupt_value(tasks, node_name: str) -> dict:
    """Extract the interrupt() payload for a named paused node.

    When a node calls interrupt(value), LangGraph freezes the node mid-execution
    and stores the value in the task's interrupts list.  The node has not yet
    returned, so its output is NOT in snapshot.values — we must read it here.
    """
    for task in (tasks or []):
        if task.name == node_name and getattr(task, "interrupts", None):
            return task.interrupts[0].value or {}
    return {}


def derive_pipeline_status(values: dict, paused_at: tuple, tasks=()) -> tuple[str, dict]:
    """Return (status, data) from a graph snapshot.

    `paused_at` is LangGraph's state.next — the node(s) currently frozen mid-execution
    by interrupt(). When a node calls interrupt(), it re-appears here because it still
    needs to finish once the client resumes.

    IMPORTANT: interrupt() pauses before the node returns, so snapshot.values does NOT
    yet contain fields the node would have written.  For HITL nodes, read the interrupt
    payload via `tasks` instead of (or as fallback to) snapshot.values.
    """
    paused_set = set(paused_at)

    if "validation" in paused_set:
        # Read from the interrupt payload — values won't have these fields yet
        iv = _read_interrupt_value(tasks, "validation")
        return "awaiting_validation", {
            "feasibility_report": iv.get("feasibility_report", values.get("feasibility_report", {})),
            "flags": iv.get("flags", values.get("flags", [])),
            "suggestions": iv.get("suggestions", values.get("suggestions", [])),
            "estimated_cost_usd": iv.get("estimated_cost_usd", values.get("estimated_cost_usd", 0.0)),
        }

    if "curriculum_review" in paused_set:
        iv = _read_interrupt_value(tasks, "curriculum_review")
        return "awaiting_curriculum_review", {
            "curriculum_plan": iv.get("curriculum_plan", values.get("curriculum_plan", {})),
            "session_content": iv.get("session_content", values.get("session_content", [])),
            "retry_count": iv.get("retry_count", values.get("retry_count", 0)),
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
