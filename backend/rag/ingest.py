"""RAG ingest helpers.

Two public entry points:
  ingest(file_paths, thread_id)   — read files (S3 keys or local paths), chunk, embed, store
  ingest_texts(texts, thread_id)  — chunk, embed, store raw (content, source) pairs

Both functions embed the chunks with OpenAI text-embedding-3-small and persist them
in AWS S3 Vectors under the given thread_id namespace.
"""
import io
import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.store import get_embeddings
from storage.s3vectors import put_vectors
from utils.logging import get_logger

logger = get_logger(__name__)

_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)


def _read_file_bytes(key_or_path: str) -> bytes | None:
    """Return raw bytes for an S3 key or a local file path.

    S3 keys start with ``uploads/``.  Anything else is treated as a local
    filesystem path (used during development without S3 configured).
    """
    if key_or_path.startswith("uploads/"):
        try:
            from storage.s3 import download_bytes
            return download_bytes(key_or_path)
        except Exception:
            logger.error("Failed to download %s from S3", key_or_path, exc_info=True)
            return None

    # Legacy local path fallback (dev without S3)
    p = Path(key_or_path)
    if not p.exists():
        logger.warning("Local file not found: %s", key_or_path)
        return None
    try:
        return p.read_bytes()
    except Exception:
        logger.error("Failed to read local file %s", key_or_path, exc_info=True)
        return None


def _read_file(key_or_path: str) -> str | None:
    """Read a PDF, txt, or md file and return its text.

    Accepts S3 object keys (``uploads/…``) or local filesystem paths.
    Returns None on any failure.
    """
    suffix = Path(key_or_path).suffix.lower()
    raw = _read_file_bytes(key_or_path)
    if raw is None:
        return None

    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix in (".txt", ".md"):
            return raw.decode("utf-8")
        else:
            logger.warning("Unsupported file format %s — skipping %s", suffix, key_or_path)
            return None
    except Exception:
        logger.error("Failed to parse %s", key_or_path, exc_info=True)
        return None


def _embed_and_store(
    texts: list[str],
    sources: list[str],
    thread_id: str,
) -> int:
    """Embed a list of text chunks and store them in S3 Vectors.

    Args:
        texts: List of chunk strings.
        sources: Parallel list of source labels (one per chunk).
        thread_id: Pipeline run identifier for namespace isolation.

    Returns:
        Number of vectors stored (0 on failure).
    """
    if not texts:
        return 0

    try:
        embeddings = get_embeddings().embed_documents(texts)
    except Exception:
        logger.error("OpenAI embedding call failed", exc_info=True)
        return 0

    chunks = [
        {
            "id": str(uuid.uuid4()),
            "embedding": emb,
            "text": text,
            "source": source,
            "chunk_index": i,
        }
        for i, (text, source, emb) in enumerate(zip(texts, sources, embeddings))
    ]

    return put_vectors(thread_id, chunks)


def ingest_texts(texts: list[tuple[str, str]], thread_id: str) -> int:
    """Chunk, embed, and store raw text strings.

    Args:
        texts: List of (content, source_label) pairs.
               source_label is stored in chunk metadata for traceability.
        thread_id: Pipeline run identifier for namespace isolation.

    Returns:
        Total number of chunks stored.
    """
    chunk_texts: list[str] = []
    chunk_sources: list[str] = []

    for content, source in texts:
        if not content:
            continue
        for chunk in _splitter.split_text(content):
            chunk_texts.append(chunk)
            chunk_sources.append(source)

    if not chunk_texts:
        logger.warning("No chunks produced from %d text source(s)", len(texts))
        return 0

    stored = _embed_and_store(chunk_texts, chunk_sources, thread_id)
    logger.info(
        "Ingested %d chunks from %d text source(s) — thread_id=%s",
        stored, len(texts), thread_id,
    )
    return stored


def ingest(file_paths: list[str], thread_id: str) -> int:
    """Chunk, embed, and store all files. Returns total number of chunks stored.

    Args:
        file_paths: S3 keys (``uploads/{batch_id}/{filename}``) or local paths.
        thread_id: Pipeline run identifier for namespace isolation.
    """
    chunk_texts: list[str] = []
    chunk_sources: list[str] = []

    for path in file_paths:
        content = _read_file(path)
        if not content:
            continue
        filename = Path(path).name
        for chunk in _splitter.split_text(content):
            chunk_texts.append(chunk)
            chunk_sources.append(filename)

    if not chunk_texts:
        logger.warning("No chunks produced from %d file(s)", len(file_paths))
        return 0

    stored = _embed_and_store(chunk_texts, chunk_sources, thread_id)
    logger.info(
        "Ingested %d chunks from %d file(s) — thread_id=%s",
        stored, len(file_paths), thread_id,
    )
    return stored
