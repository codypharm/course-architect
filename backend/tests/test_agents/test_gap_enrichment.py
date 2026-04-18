import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.gap_enrichment import gap_enrichment_agent, _extract_texts
from schemas.preprocessor import KnowledgeSummary

MINIMAL_STATE = {
    "subject": "Python Programming",
    "audience_age": "16-18 years",
    "audience_level": "beginner",
    "knowledge_summary": {
        "content_overview": "Covers variables and loops.",
        "total_topics": ["variables", "loops"],
        "coverage_depth": "introductory",
        "total_teaching_minutes": 60,
        "prerequisites": ["basic computer literacy"],
        "gaps": ["functions", "error handling"],
        "fit_for_audience": "Good fit.",
        "fit_for_duration": "Needs more content.",
        "recommendations": [],
    },
}

UPDATED_SUMMARY = KnowledgeSummary(
    content_overview="Covers variables, loops, functions, and error handling.",
    total_topics=["variables", "loops", "functions", "error handling"],
    coverage_depth="introductory",
    total_teaching_minutes=60,
    prerequisites=["basic computer literacy"],
    gaps=[],
    fit_for_audience="Good fit.",
    fit_for_duration="Content now covers more sessions.",
    recommendations=[],
)

SAMPLE_RESULTS = [
    {"content": "Functions in Python are defined with the def keyword.", "url": "https://example.com/functions"},
    {"content": "Error handling uses try/except blocks.", "url": "https://example.com/errors"},
]


def _make_tool_message(results: list[dict]) -> ToolMessage:
    return ToolMessage(content=json.dumps({"results": results}), tool_call_id="call_123")


def _make_agent_result(tool_messages: list[ToolMessage]) -> dict:
    return {
        "messages": [
            HumanMessage(content="Search for gaps."),
            AIMessage(content="", tool_calls=[{"id": "call_123", "name": "tavily_search", "args": {}}]),
            *tool_messages,
            AIMessage(content="Done searching."),
        ]
    }


def _mock_mcp():
    mock = AsyncMock()
    mock.get_tools.return_value = []
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


@pytest.mark.anyio
async def test_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    result = await gap_enrichment_agent(MINIMAL_STATE)
    assert result == {}


@pytest.mark.anyio
async def test_ingests_and_returns_updated_knowledge_summary(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    mock_agent = AsyncMock()
    # Agent returns tool messages + a final summary message
    summary_msg = AIMessage(content="- functions: def keyword defines functions\n- error handling: try/except blocks")
    agent_result = _make_agent_result([_make_tool_message(SAMPLE_RESULTS)])
    agent_result["messages"].append(summary_msg)
    mock_agent.ainvoke.return_value = agent_result

    mock_synthesizer = AsyncMock()
    mock_synthesizer.ainvoke.return_value = UPDATED_SUMMARY

    with patch("agents.gap_enrichment.MultiServerMCPClient", return_value=_mock_mcp()), \
         patch("agents.gap_enrichment.create_react_agent", return_value=mock_agent), \
         patch("agents.gap_enrichment.init_chat_model"), \
         patch("agents.gap_enrichment._get_synthesizer", return_value=mock_synthesizer), \
         patch("agents.gap_enrichment.ingest_texts", return_value=4) as mock_ingest:
        result = await gap_enrichment_agent(MINIMAL_STATE)

    mock_ingest.assert_called_once()
    assert "knowledge_summary" in result
    summary = result["knowledge_summary"]
    assert summary["gaps"] == []
    assert "functions" in summary["total_topics"]
    assert "error handling" in summary["total_topics"]
    assert "variables" in summary["total_topics"]


@pytest.mark.anyio
async def test_skips_empty_content_results(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    tool_msgs = [_make_tool_message([
        {"content": "", "url": "https://example.com/empty"},
        {"content": "Good content here.", "url": "https://example.com/good"},
    ])]
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = _make_agent_result(tool_msgs)

    mock_synthesizer = AsyncMock()
    mock_synthesizer.ainvoke.return_value = UPDATED_SUMMARY

    with patch("agents.gap_enrichment.MultiServerMCPClient", return_value=_mock_mcp()), \
         patch("agents.gap_enrichment.create_react_agent", return_value=mock_agent), \
         patch("agents.gap_enrichment.init_chat_model"), \
         patch("agents.gap_enrichment._get_synthesizer", return_value=mock_synthesizer), \
         patch("agents.gap_enrichment.ingest_texts", return_value=1) as mock_ingest:
        await gap_enrichment_agent(MINIMAL_STATE)

    ingested = mock_ingest.call_args[0][0]
    assert len(ingested) == 1
    assert ingested[0][0] == "Good content here."


@pytest.mark.anyio
async def test_returns_empty_when_no_content_extracted(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {"messages": [AIMessage(content="No results found.")]}

    with patch("agents.gap_enrichment.MultiServerMCPClient", return_value=_mock_mcp()), \
         patch("agents.gap_enrichment.create_react_agent", return_value=mock_agent), \
         patch("agents.gap_enrichment.init_chat_model"), \
         patch("agents.gap_enrichment.ingest_texts") as mock_ingest:
        result = await gap_enrichment_agent(MINIMAL_STATE)

    mock_ingest.assert_not_called()
    assert result == {}


def test_extract_texts_handles_non_json_tool_message():
    msg = ToolMessage(content="Plain text result", tool_call_id="call_1")
    texts = _extract_texts([msg])
    assert len(texts) == 1
    assert texts[0][0] == "Plain text result"
