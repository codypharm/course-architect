"""LangGraph pipeline definition for AI Course Architect.

START
  ↓
preprocessor
  ↓
validation  (HITL #1 — tutor approves feasibility report)
  ↓ _after_validation
  ├─ not approved      → END
  ├─ approved + gaps   → gap_enrichment → curriculum_planner
  └─ approved, no gaps → curriculum_planner
                               ↓
                       curriculum_review  (HITL #2 — tutor approves generated plan)
                         ↓ _after_review
                         ├─ approved → END
                         └─ retry    → curriculum_planner  (retry_context injected as HARD CONSTRAINT)

Checkpointer: RedisSaver — shared across all Celery workers and the API process so that
graph state persists between task runs and survives worker restarts.
Phase 2: swap REDIS_URL to point at ElastiCache; swap RedisSaver → AsyncPostgresSaver for Aurora.
"""
import os

import redis as redis_lib
from dotenv import load_dotenv
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, START, StateGraph

load_dotenv()

_REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = redis_lib.from_url(_REDIS_URL)
_checkpointer = RedisSaver(_redis_client)

from nodes.curriculum_planner import curriculum_planner_agent
from nodes.curriculum_review import curriculum_review_node
from nodes.gap_enrichment import gap_enrichment_agent
from nodes.preprocessor import knowledge_base_preprocessor
from nodes.validation import validation_agent
from graph.state import CourseState


def _after_validation(state: CourseState) -> str:
    """After validation HITL: abort if not approved, otherwise check for gaps."""
    if not state.get("user_approved"):
        return END
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
    builder.add_conditional_edges("validation", _after_validation, {
        "gap_enrichment": "gap_enrichment",
        "curriculum_planner": "curriculum_planner",
        END: END,
    })
    builder.add_edge("gap_enrichment", "curriculum_planner")
    builder.add_edge("curriculum_planner", "curriculum_review")
    builder.add_conditional_edges("curriculum_review", _after_review, {
        "curriculum_planner": "curriculum_planner",
        END: END,
    })

    return builder.compile(checkpointer=_checkpointer, interrupt_before=[])


# Module-level compiled graph used by API / Celery tasks
graph = build_graph()
