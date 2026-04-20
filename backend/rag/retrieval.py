"""RAG retrieval helper.

Public API:
  retrieve(query, thread_id, k=5) → str

Embeds the query, fetches the top-k*2 nearest vectors from S3 Vectors for the
given thread_id, reranks them with a small LLM call, and returns the top-k
chunks as a single newline-delimited string ready to inject into an agent prompt.
"""
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from rag.store import get_embeddings
from storage.s3vectors import query_vectors
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
    """Lazily initialise the reranker LLM."""
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
        seen: set[int] = set()
        deduped = [i for i in valid if not (i in seen or seen.add(i))]  # type: ignore[func-returns-value]
        missing = [i for i in range(len(chunks)) if i not in seen]
        return [chunks[i] for i in deduped + missing]
    except Exception:
        logger.warning("Reranking failed — returning original order", exc_info=True)
        return chunks


def retrieve(query: str, thread_id: str, k: int = 5) -> str:
    """Fetch k chunks from S3 Vectors, rerank by relevance, and return as a joined string.

    Args:
        query: Search query to embed and match against stored chunks.
        thread_id: Pipeline run identifier — limits results to this run's vectors.
        k: Number of chunks to return after reranking.

    Returns:
        Chunks joined with '\\n\\n---\\n\\n', ready to inject into a prompt.
        Empty string if the store has no results for this thread.
    """
    try:
        query_embedding = get_embeddings().embed_query(query)
    except Exception:
        logger.error("Failed to embed query", exc_info=True)
        return ""

    results = query_vectors(thread_id, query_embedding, top_k=k * 2)
    if not results:
        return ""

    chunks = [r["metadata"]["text"] for r in results if r.get("metadata", {}).get("text")]
    if not chunks:
        return ""

    reranked = _rerank(query, chunks)
    logger.info(
        "Retrieved and reranked %d chunks for query: %.60s… — thread_id=%s",
        len(reranked), query, thread_id,
    )
    return "\n\n---\n\n".join(reranked[:k])
