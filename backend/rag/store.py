"""Shared OpenAI embeddings singleton for the RAG pipeline.

Both rag/ingest.py and rag/retrieval.py import get_embeddings() from here
so the model is initialised exactly once per process.
"""
from langchain_openai import OpenAIEmbeddings

_embeddings: OpenAIEmbeddings | None = None


def get_embeddings() -> OpenAIEmbeddings:
    """Return the shared OpenAI embeddings model, initialised on first call."""
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return _embeddings
