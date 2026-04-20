"""RAG ingest helpers.

Two public entry points:
  ingest(file_paths)   — read files (S3 keys or local paths), chunk, embed, store
  ingest_texts(texts)  — chunk, embed, store raw (content, source) pairs
"""
import io
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.store import get_store
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


def ingest_texts(texts: list[tuple[str, str]]) -> int:
    """Chunk, embed, and store raw text strings.

    Args:
        texts: list of (content, source_label) pairs.
               source_label is stored in chunk metadata for DB traceability.

    Returns:
        Total number of chunks stored.
    """
    store = get_store()
    docs: list[Document] = []

    for content, source in texts:
        if not content:
            continue
        chunks = _splitter.split_text(content)
        for i, chunk in enumerate(chunks):
            docs.append(Document(page_content=chunk, metadata={"source": source, "chunk_index": i}))

    if not docs:
        logger.warning("No chunks produced from %d text source(s)", len(texts))
        return 0

    store.add_documents(docs)
    logger.info("Ingested %d chunks from %d text source(s)", len(docs), len(texts))
    return len(docs)


def ingest(file_paths: list[str]) -> int:
    """Chunk, embed, and store all files. Returns total number of chunks stored.

    Args:
        file_paths: S3 keys (``uploads/{batch_id}/{filename}``) or local paths.
    """
    store = get_store()
    docs: list[Document] = []

    for path in file_paths:
        content = _read_file(path)
        if not content:
            continue
        chunks = _splitter.split_text(content)
        filename = Path(path).name
        for i, chunk in enumerate(chunks):
            docs.append(Document(page_content=chunk, metadata={"source": filename, "chunk_index": i}))

    if not docs:
        logger.warning("No chunks produced from %d file(s)", len(file_paths))
        return 0

    store.add_documents(docs)
    logger.info("Ingested %d chunks from %d file(s)", len(docs), len(file_paths))
    return len(docs)
