"""Gap enrichment node.

Uses a LangGraph ReAct agent with the Serper MCP server (stdio via uvx) so the
LLM can phrase targeted Google Search queries for each knowledge gap and decide
when it has found enough content.

Serper wraps Google Search — fast, reliable, 2 500 free searches/month.
The MCP server (`mcp-server-serper`) runs locally via `uvx` (no Node.js needed).

Results are:
  1. Ingested into the vector store via ingest_texts()
  2. Synthesised via a structured LLM call into an updated KnowledgeSummary
     (gaps cleared, total_topics updated, content_overview revised)

On any failure (missing API key, MCP error, no results) gaps are cleared so the
pipeline advances to the curriculum planner without stalling.
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

Use the available search tool once per gap with a focused, educational query —
e.g. "introduction to <topic> for <audience_level> students". One search per gap
is sufficient; prioritise clear explanations over quantity.

When you are done searching, write a concise summary of what you found for each gap.
For each gap, list the key concepts, definitions, and teaching points — in bullet points.
This summary will be used to update the course knowledge base, so preserve all important points.
"""

_SYNTHESIS_PROMPT = """You are updating a course knowledge base summary after new content was retrieved to fill gaps.

Original knowledge summary:
{original_summary}

Gaps that were enriched with new content:
{gaps}

Newly retrieved content:
{content_sample}

Produce an updated KnowledgeSummary that:
- Moves the enriched gaps into total_topics (remove them from gaps)
- Updates content_overview to mention the newly available topics
- Updates total_teaching_minutes to add a reasonable estimate for the newly enriched topics
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
    """Extract (content, url) pairs from Serper MCP ToolMessage responses.

    Serper returns JSON with an 'organic' array where each item has
    'snippet' (content), 'link' (url), and 'title'.  Falls back to treating
    the raw message content as plain text if JSON parsing fails.

    ToolMessage.content may be an empty string when the MCP server wraps the
    actual payload in ToolMessage.artifact or as a list of content blocks.
    We inspect all three locations.
    """
    texts = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue

        tool_name = getattr(msg, "name", "unknown")

        logger.debug(
            "ToolMessage from Serper — tool=%s content_type=%s",
            tool_name,
            type(msg.content).__name__,
        )

        # Collect candidate raw payloads to try parsing
        candidates: list = []

        # 1. Primary: msg.content (string or list of content blocks)
        if isinstance(msg.content, str) and msg.content.strip():
            candidates.append(msg.content)
        elif isinstance(msg.content, list):
            # Content blocks: [{"type": "text", "text": "..."}, ...]
            for block in msg.content:
                if isinstance(block, dict):
                    text = block.get("text") or block.get("content") or ""
                    if text:
                        candidates.append(text)
                elif isinstance(block, str) and block.strip():
                    candidates.append(block)

        # 2. Fallback: msg.artifact (some MCP adapters put structured data here)
        artifact = getattr(msg, "artifact", None)
        if artifact is not None:
            candidates.append(artifact)

        if not candidates:
            logger.warning("ToolMessage from %s has no usable content or artifact", tool_name)
            continue

        for raw in candidates:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(data, dict):
                    # Serper organic results: {"organic": [{"snippet", "link", "title"}, ...]}
                    for result in data.get("organic", []):
                        content = result.get("snippet") or result.get("content") or ""
                        url     = result.get("link") or result.get("url") or "serper_result"
                        if content.strip():
                            texts.append((content, url))
                    # Answer box / knowledge graph (bonus content when present)
                    answer = (
                        data.get("answerBox", {}).get("answer")
                        or data.get("answerBox", {}).get("snippet")
                        or ""
                    )
                    if answer.strip():
                        texts.append((answer, "serper_answer_box"))
                    # Some wrappers return {"results": [...]}
                    for result in data.get("results", []):
                        content = result.get("snippet") or result.get("content") or result.get("body") or ""
                        url     = result.get("link") or result.get("url") or "serper_result"
                        if content.strip():
                            texts.append((content, url))
                elif isinstance(data, list):
                    # Top-level array of result objects
                    for result in data:
                        if isinstance(result, dict):
                            content = result.get("snippet") or result.get("content") or result.get("body") or ""
                            url     = result.get("link") or result.get("url") or "serper_result"
                            if content.strip():
                                texts.append((content, url))
            except (json.JSONDecodeError, TypeError, AttributeError):
                # Non-JSON response — use as plain text
                if isinstance(raw, str) and raw.strip():
                    texts.append((raw, "serper_result"))

    return texts


async def _synthesize(
    original_summary: dict,
    gaps: list[str],
    content: str,
) -> KnowledgeSummary:
    """Run a structured LLM call to produce an updated KnowledgeSummary."""
    synthesizer = _get_synthesizer()
    return await synthesizer.ainvoke([
        HumanMessage(content=_SYNTHESIS_PROMPT.format(
            original_summary=json.dumps(original_summary, indent=2),
            gaps="\n".join(f"- {g}" for g in gaps),
            content_sample=content,
        ))
    ])


async def gap_enrichment_agent(state: CourseState) -> dict:
    """LangGraph node. Runs a ReAct agent with the Serper MCP server (stdio/uvx)
    to search Google for content filling each knowledge gap.

    Results are ingested into the vector store and a structured LLM call produces
    an updated KnowledgeSummary with gaps cleared.

    On any failure (missing API key, MCP error, no results) gaps are cleared so
    the pipeline advances to the curriculum planner without stalling.
    """
    knowledge_summary: dict = state.get("knowledge_summary", {})
    gaps: list[str]         = knowledge_summary.get("gaps", [])

    def _clear_gaps() -> dict:
        """Return knowledge_summary with gaps cleared."""
        cleared = dict(knowledge_summary)
        cleared["gaps"] = []
        return {"knowledge_summary": cleared}

    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        logger.warning("SERPER_API_KEY not set — skipping gap enrichment, clearing gaps")
        return _clear_gaps()

    if not gaps:
        logger.info("No gaps to enrich — skipping")
        return {}

    logger.info("Enriching %d gap(s) via Serper MCP: %s", len(gaps), ", ".join(gaps))

    # stdio transport — spawns the Serper MCP server via npx.
    # npx downloads and runs the package on first use; requires Node.js >= 18.
    mcp_client = MultiServerMCPClient({
        "serper": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "serper-search-scrape-mcp-server"],
            "env": {**os.environ, "SERPER_API_KEY": api_key},
        }
    })

    try:
        tools = await mcp_client.get_tools()
    except Exception:
        logger.warning("Serper MCP tool discovery failed — clearing gaps so pipeline advances", exc_info=True)
        return _clear_gaps()

    logger.info("Serper MCP tools available: %s", [t.name for t in tools])

    llm   = init_chat_model(model="gpt-4o-mini", temperature=0)
    agent = create_react_agent(llm, tools)

    prompt = _SEARCH_PROMPT.format(
        subject=state.get("subject", ""),
        audience_age=state.get("audience_age", ""),
        audience_level=state.get("audience_level", ""),
        gaps="\n".join(f"- {gap}" for gap in gaps),
    )

    try:
        result = await agent.ainvoke({
            "messages": [
                SystemMessage(content=prompt),
                HumanMessage(content="Search for content to fill each of the knowledge gaps listed above."),
            ]
        })
    except Exception:
        # MCP subprocess errors are non-fatal — enrichment is supplementary.
        logger.warning("Serper MCP agent call failed — clearing gaps so pipeline advances", exc_info=True)
        return _clear_gaps()

    texts = _extract_texts(result["messages"])

    if not texts:
        logger.warning("No usable content extracted from Serper MCP results — clearing gaps so pipeline advances")
        return _clear_gaps()

    # Ingest full raw content into vector store for RAG retrieval at generation time
    chunk_count = ingest_texts(texts, thread_id=state["thread_id"])
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

    # Fall back to raw snippets if the agent produced no summary
    if not synthesis_content:
        synthesis_content = "\n\n---\n\n".join(text for text, _ in texts)

    updated_summary = await _synthesize(knowledge_summary, gaps, synthesis_content)
    logger.info(
        "Knowledge summary updated — topics: %d, gaps remaining: %d",
        len(updated_summary.total_topics), len(updated_summary.gaps),
    )

    return {"knowledge_summary": updated_summary.model_dump()}
