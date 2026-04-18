from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

_store: InMemoryVectorStore | None = None


def get_store() -> InMemoryVectorStore:
    """Return the current vector store, initialising it on first call."""
    global _store
    if _store is None:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        _store = InMemoryVectorStore(embedding=embeddings)
    return _store


def reset_store() -> None:
    """Clear the vector store. Call between runs to avoid cross-run contamination."""
    global _store
    _store = None
