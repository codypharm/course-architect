"""Shared LangChain tools used by agent nodes."""
from langchain_core.tools import tool

from rag.retrieval import retrieve


@tool
def query_knowledge_base(query: str) -> str:
    """Search the course knowledge base for content relevant to a session topic.
    Call this once per session topic to retrieve teaching material before planning it."""
    result = retrieve(query=query, k=5)
    return result if result else "No relevant content found for this query."
