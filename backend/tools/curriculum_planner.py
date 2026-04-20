"""Shared LangChain tools used by agent nodes."""
from langchain_core.tools import tool

from rag.retrieval import retrieve


def build_query_tool(thread_id: str):
    """Return a knowledge-base query tool scoped to a specific pipeline run.

    The tool captures thread_id in a closure so every call to query_knowledge_base
    is automatically scoped to the correct S3 Vectors namespace without requiring
    the agent to pass thread_id explicitly.

    Args:
        thread_id: Pipeline run identifier — limits retrieval to this run's vectors.
    """
    @tool
    def query_knowledge_base(query: str) -> str:
        """Search the course knowledge base for content relevant to a session topic.
        Call this once per session topic to retrieve teaching material before planning it."""
        result = retrieve(query=query, thread_id=thread_id, k=5)
        return result if result else "No relevant content found for this query."

    return query_knowledge_base
