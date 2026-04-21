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

Checkpointer:
  - Production (Aurora Postgres): AsyncPostgresSaver — persists across Celery workers and API restarts.
  - Local dev (SQLite): MemorySaver — in-process only, no extra infra needed.

ElastiCache is plain Redis and does not include the RediSearch module, so
langgraph-checkpoint-redis (which requires FT._LIST from Redis Stack) cannot be used.
"""
import os

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv()

from storage.database import DATABASE_URL

_is_postgres = DATABASE_URL.startswith("postgresql")

if _is_postgres:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    # psycopg uses standard postgresql:// URLs; strip the +asyncpg SQLAlchemy driver prefix
    _PG_CONN_STR = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    if os.getenv("DB_HOST"):
        # Aurora requires SSL; append only when running on ECS (DB_HOST is set by Terraform)
        _PG_CONN_STR += "?sslmode=require"
    _checkpointer = AsyncPostgresSaver.from_conn_string(_PG_CONN_STR)
else:
    from langgraph.checkpoint.memory import MemorySaver
    _checkpointer = MemorySaver()

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


def build_graph(checkpointer=None):
    """Construct and compile the LangGraph pipeline.

    Accepts an optional checkpointer so Celery tasks can supply a freshly
    created AsyncRedisSaver bound to the current event loop.  When omitted
    the module-level AsyncRedisSaver (suitable for the long-lived FastAPI
    event loop) is used.
    """
    cp = checkpointer if checkpointer is not None else _checkpointer

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

    return builder.compile(checkpointer=cp, interrupt_before=[])


# Module-level compiled graph — used by the FastAPI process only.
# Celery tasks must NOT use this instance; each task builds its own graph
# with a fresh AsyncRedisSaver so connections stay bound to the correct
# event loop (asyncio.run() creates a new loop per task invocation).
graph = build_graph()
