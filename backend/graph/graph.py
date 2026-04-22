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
    from psycopg_pool import AsyncConnectionPool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    # psycopg uses standard postgresql:// URLs; strip the +asyncpg SQLAlchemy driver prefix
    _PG_CONN_STR = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    if os.getenv("DB_HOST"):
        # Aurora requires SSL; append only when running on ECS (DB_HOST is set by Terraform)
        _PG_CONN_STR += "?sslmode=require"
    # Pool is created closed at module level — safe to construct without a running event loop.
    # AsyncPostgresSaver is NOT created here because its __init__ calls
    # asyncio.get_running_loop(), which raises RuntimeError when graph.py is imported
    # by the Celery worker (synchronous process, no event loop at import time).
    # open_checkpointer() runs inside FastAPI's async lifespan and creates it there.
    _pg_pool = AsyncConnectionPool(
        conninfo=_PG_CONN_STR,
        open=False,
        kwargs={"autocommit": True},
    )
    _checkpointer = None  # set by open_checkpointer() once the event loop is running

    async def open_checkpointer() -> None:
        """Open the connection pool and create checkpoint tables (idempotent).

        Called from FastAPI lifespan — a running event loop is guaranteed here.
        AsyncPostgresSaver is constructed here (not at module level) specifically
        because its __init__ calls asyncio.get_running_loop().
        """
        global _checkpointer, graph
        await _pg_pool.open()
        _checkpointer = AsyncPostgresSaver(_pg_pool)
        await _checkpointer.setup()
        # Recompile the module-level graph now that the checkpointer is ready.
        # build_graph() at import time ran with _checkpointer=None; FastAPI's
        # get_course endpoint calls graph.aget_state() which requires a checkpointer.
        graph = build_graph(_checkpointer)

    async def close_checkpointer() -> None:
        """Close the connection pool on app shutdown."""
        await _pg_pool.close()

else:
    from langgraph.checkpoint.memory import MemorySaver
    _checkpointer = MemorySaver()

    async def open_checkpointer() -> None:
        """No-op for local dev MemorySaver."""

    async def close_checkpointer() -> None:
        """No-op for local dev MemorySaver."""

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

    Callers:
    - FastAPI: called without arguments after open_checkpointer() sets _checkpointer.
    - Celery tasks: always pass their own fresh AsyncPostgresSaver so that
      connections are bound to the task's event loop, not the FastAPI loop.

    _checkpointer may be None when this is called at module level during Celery
    worker startup (before any event loop exists). That's fine — the module-level
    graph singleton is only used by FastAPI; Celery tasks call build_graph(cp)
    with an explicit checkpointer each time.
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
