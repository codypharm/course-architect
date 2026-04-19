"""Gap enrichment node.

Uses a LangGraph ReAct agent with the Tavily MCP server so the LLM can phrase
targeted search queries for each knowledge gap and decide when it has found
enough content. Results are:
  1. Ingested into the vector store via ingest_texts()
  2. Synthesised via a structured LLM call into an updated KnowledgeSummary
     (gaps cleared, total_topics updated, content_overview revised)

Requires Node.js on the host machine (used to run tavily-mcp via npx).
"""
import json
import os

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from graph.state import CourseState
from rag.ingest import ingest_texts
from schemas.preprocessor import KnowledgeSummary
from utils.logging import get_logger

logger = get_logger(__name__)

_SEARCH_PROMPT = """You are a knowledge base enrichment agent for course planning.

Course context:
- Subject: {subject}
- Audience Age: {audience_age}
- Audience Level: {audience_level}

The knowledge base is missing content on the following topics:
{gaps}

Search for clear, educational content that would help teach each missing topic to this audience.
One or two focused searches per gap is enough — prioritise quality explanations over quantity.

When you are done searching, write a concise summary of what you found for each gap.
For each gap, list the key concepts, definitions, and teaching points found — in bullet points.
This summary will be used to update the course knowledge base, so preserve all important points.
"""

_SYNTHESIS_PROMPT = """You are updating a course knowledge base summary after new content was retrieved to fill gaps.

Original knowledge summary:
{original_summary}

Gaps that were enriched with new content:
{gaps}

Newly Retrieved content (all results):
{content_sample}

Produce an updated KnowledgeSummary that:
- Moves the enriched gaps into total_topics (remove them from gaps)
- Updates content_overview to mention the newly available topics
- Updates total_teaching_minutes to add a reasonable estimate for the newly enriched topics (base it on the retrieved content volume)
- Do NOT invent topics beyond the enriched gaps listed above
- Sets gaps to only topics that were NOT enriched (empty list if all gaps were filled)
"""

_llm = None
_synthesizer = None


def _get_synthesizer():
    """Lazily initialise the structured output LLM for synthesis."""
    global _llm, _synthesizer
    if _llm is None:
        _llm = init_chat_model(model="gpt-4o-mini", temperature=0)
        _synthesizer = _llm.with_structured_output(KnowledgeSummary)
    return _synthesizer


def _extract_texts(messages: list) -> list[tuple[str, str]]:
    """Extract (content, url) pairs from Tavily ToolMessage responses."""
    texts = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        try:
            data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            for result in data.get("results", []):
                content = result.get("content") or ""
                url = result.get("url") or "search_result"
                if content.strip():
                    texts.append((content, url))
        except (json.JSONDecodeError, TypeError, AttributeError):
            # Non-JSON tool response — use as-is
            if isinstance(msg.content, str) and msg.content.strip():
                texts.append((msg.content, "search_result"))
    return texts


async def _synthesize(
    original_summary: dict,
    gaps: list[str],
    content: str,
) -> KnowledgeSummary:
    """Run a structured LLM call to produce an updated KnowledgeSummary.

    Args:
        original_summary: The existing knowledge_summary dict from state.
        gaps: The gap topics that were enriched.
        content: Summarised content from the search agent (or raw fallback), capped at 20k chars.

    Returns:
        Updated KnowledgeSummary with gaps cleared and topics merged.
    """
    synthesizer = _get_synthesizer()
    return await synthesizer.ainvoke([
        HumanMessage(content=_SYNTHESIS_PROMPT.format(
            original_summary=json.dumps(original_summary, indent=2),
            gaps="\n".join(f"- {g}" for g in gaps),
            content_sample=content,
        ))
    ])


async def gap_enrichment_agent(state: CourseState) -> dict:
    """LangGraph node. Runs a ReAct agent with the Tavily MCP server to search
    for content filling each knowledge gap. The LLM phrases its own queries based
    on the course context. Search results are ingested into the vector store and
    a structured LLM call produces an updated KnowledgeSummary with gaps cleared."""
    knowledge_summary: dict = state.get("knowledge_summary", {})
    gaps: list[str] = knowledge_summary.get("gaps", [])

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set — skipping gap enrichment, clearing gaps")
        cleared = dict(knowledge_summary)
        cleared["gaps"] = []
        return {"knowledge_summary": cleared}

    logger.info("Enriching %d gap(s) via Tavily MCP: %s", len(gaps), ", ".join(gaps))

    # langchain-mcp-adapters >= 0.1.0 removed async context manager support.
    # Use get_tools() directly on the client instance instead.
    mcp_client = MultiServerMCPClient(
        {
            "tavily": {
                "command": "npx",
                "args": ["-y", "tavily-mcp@0.1.4"],
                "env": {**os.environ, "TAVILY_API_KEY": api_key},
                "transport": "stdio",
            }
        }
    )
    tools = await mcp_client.get_tools()
    llm = init_chat_model(model="gpt-4o-mini", temperature=0)
    agent = create_react_agent(llm, tools)

    prompt = _SEARCH_PROMPT.format(
        subject=state.get("subject", ""),
        audience_age=state.get("audience_age", ""),
        audience_level=state.get("audience_level", ""),
        gaps="\n".join(f"- {gap}" for gap in gaps),
    )

    result = await agent.ainvoke({
        "messages": [
            SystemMessage(content=prompt),
            HumanMessage(content="Search for content to fill each of the knowledge gaps listed above."),
        ]
    })

    texts = _extract_texts(result["messages"])

    if not texts:
        logger.warning("No usable content extracted from MCP search results — clearing gaps so pipeline advances")
        # Return knowledge_summary with gaps cleared so infer_processing_stage
        # correctly reports stage 3 (curriculum planner) instead of stage 2 (enriching).
        cleared = dict(knowledge_summary)
        cleared["gaps"] = []
        return {"knowledge_summary": cleared}

    # Ingest full raw content into vector store (keeps full detail for RAG retrieval)
    chunk_count = ingest_texts(texts)
    logger.info(
        "Ingested %d result(s) → %d chunks for %d gap(s)",
        len(texts), chunk_count, len(gaps),
    )

    # Use the agent's final summarised message for synthesis — cleaner than raw tool output
    final_ai_messages = [
        m for m in result["messages"]
        if isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None)
    ]
    synthesis_content = final_ai_messages[-1].content if final_ai_messages else ""

    # Fall back to raw texts if agent produced no summary
    if not synthesis_content:
        synthesis_content = "\n\n---\n\n".join(text for text, _ in texts)

    # Structured synthesis — updated KnowledgeSummary with gaps cleared
    updated_summary = await _synthesize(knowledge_summary, gaps, synthesis_content)
    logger.info("Knowledge summary updated — topics: %d, gaps remaining: %d",
                len(updated_summary.total_topics), len(updated_summary.gaps))

    return {"knowledge_summary": updated_summary.model_dump()}
