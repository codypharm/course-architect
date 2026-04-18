from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from rag.store import get_store
from utils.logging import get_logger

logger = get_logger(__name__)

_RERANK_PROMPT = """You are a relevance judge. Given a query and a list of text chunks, rank the chunks by how useful they are for answering the query.

Query: {query}

Chunks:
{chunks}

Return the indices of the chunks in order from most relevant to least relevant.
Use 0-based indexing. Include all {count} indices."""


class _RerankOutput(BaseModel):
    ranked_indices: list[int]


_llm = None
_reranker = None


def _get_reranker():
    global _llm, _reranker
    if _llm is None:
        _llm = init_chat_model(model="gpt-4o-mini", temperature=0)
        _reranker = _llm.with_structured_output(_RerankOutput)
    return _reranker


def _rerank(query: str, chunks: list[str]) -> list[str]:
    """Rerank chunks by relevance to query using a single LLM call."""
    if len(chunks) <= 1:
        return chunks
    try:
        numbered = "\n\n".join(f"[{i}] {chunk}" for i, chunk in enumerate(chunks))
        result = _get_reranker().invoke([
            HumanMessage(content=_RERANK_PROMPT.format(
                query=query,
                chunks=numbered,
                count=len(chunks),
            ))
        ])
        valid = [i for i in result.ranked_indices if 0 <= i < len(chunks)]
        seen = set()
        deduped = [i for i in valid if not (i in seen or seen.add(i))]
        missing = [i for i in range(len(chunks)) if i not in seen]
        return [chunks[i] for i in deduped + missing]
    except Exception:
        logger.warning("Reranking failed — returning original order", exc_info=True)
        return chunks


def retrieve(query: str, k: int = 5) -> str:
    """Fetch k chunks from the vector store, rerank by relevance, and return as a joined string.

    The returned string is ready to inject directly into an agent's system prompt.
    Returns an empty string if the store is empty or no results are found.
    """
    store = get_store()
    results = store.similarity_search(query, k=k)
    if not results:
        return ""

    chunks = [doc.page_content for doc in results]
    reranked = _rerank(query, chunks)
    logger.info("Retrieved and reranked %d chunks for query: %.60s...", len(reranked), query)
    return "\n\n---\n\n".join(reranked)
