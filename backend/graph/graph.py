"""LangGraph pipeline definition for AI Course Architect.

Graph structure:
    preprocessor → validation → gap_enrichment (conditional) → curriculum_planner

The HITL checkpoint lives inside validation_agent (LangGraph interrupt()).
The gap enrichment node is skipped when there are no gaps in the knowledge summary.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.curriculum_planner import curriculum_planner_agent
from agents.gap_enrichment import gap_enrichment_agent
from agents.preprocessor import knowledge_base_preprocessor
from agents.validation import validation_agent
from graph.state import CourseState


def _should_enrich(state: CourseState) -> str:
    """Conditional edge: route to gap_enrichment only when gaps exist."""
    gaps = state.get("knowledge_summary", {}).get("gaps", [])
    return "gap_enrichment" if gaps else "curriculum_planner"


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph pipeline."""
    builder = StateGraph(CourseState)

    # Nodes
    builder.add_node("preprocessor", knowledge_base_preprocessor)
    builder.add_node("validation", validation_agent)
    builder.add_node("gap_enrichment", gap_enrichment_agent)
    builder.add_node("curriculum_planner", curriculum_planner_agent)

    # Edges
    builder.add_edge(START, "preprocessor")
    builder.add_edge("preprocessor", "validation")
    # After HITL approval inside validation, check whether gaps need filling
    builder.add_conditional_edges("validation", _should_enrich, ["gap_enrichment", "curriculum_planner"])
    builder.add_edge("gap_enrichment", "curriculum_planner")
    builder.add_edge("curriculum_planner", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer, interrupt_before=[])


# Module-level compiled graph used by API / Celery tasks
graph = build_graph()
