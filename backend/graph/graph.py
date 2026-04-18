"""LangGraph pipeline definition for AI Course Architect.

Graph structure:
    preprocessor → validation (HITL #1) → gap_enrichment? → curriculum_planner
                                                                     ↓
                                                          curriculum_review (HITL #2)
                                                         /                         \
                                                   (approved)                   (retry)
                                                       ↓                           ↓
                                                      END               curriculum_planner

HITL #1 (validation): tutor reviews feasibility report, approves or revises brief.
HITL #2 (curriculum_review): tutor reviews generated plan, approves or requests retry.
On retry, curriculum_review writes retry_context to state; curriculum_planner picks it
up via _build_constraint_block() and injects it as a HARD CONSTRAINT into the prompt.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.curriculum_planner import curriculum_planner_agent
from agents.curriculum_review import curriculum_review_node
from agents.gap_enrichment import gap_enrichment_agent
from agents.preprocessor import knowledge_base_preprocessor
from agents.validation import validation_agent
from graph.state import CourseState


def _should_enrich(state: CourseState) -> str:
    """Route to gap_enrichment when the knowledge summary has unfilled gaps."""
    gaps = state.get("knowledge_summary", {}).get("gaps", [])
    return "gap_enrichment" if gaps else "curriculum_planner"


def _after_review(state: CourseState) -> str:
    """Route to END when approved, back to curriculum_planner when retry requested."""
    return END if state.get("curriculum_approved") else "curriculum_planner"


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph pipeline."""
    builder = StateGraph(CourseState)

    # Nodes
    builder.add_node("preprocessor", knowledge_base_preprocessor)
    builder.add_node("validation", validation_agent)
    builder.add_node("gap_enrichment", gap_enrichment_agent)
    builder.add_node("curriculum_planner", curriculum_planner_agent)
    builder.add_node("curriculum_review", curriculum_review_node)

    # Edges
    builder.add_edge(START, "preprocessor")
    builder.add_edge("preprocessor", "validation")
    builder.add_conditional_edges("validation", _should_enrich, ["gap_enrichment", "curriculum_planner"])
    builder.add_edge("gap_enrichment", "curriculum_planner")
    builder.add_edge("curriculum_planner", "curriculum_review")
    builder.add_conditional_edges("curriculum_review", _after_review, ["curriculum_planner", END])

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer, interrupt_before=[])


# Module-level compiled graph used by API / Celery tasks
graph = build_graph()
