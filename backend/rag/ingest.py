from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag.store import get_store
from utils.logging import get_logger

logger = get_logger(__name__)

_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)


def _read_file(path: str) -> str | None:
    """Read a PDF, txt, or md file and return its text. Returns None on any failure."""
    p = Path(path)
    try:
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix in (".txt", ".md"):
            return p.read_text(encoding="utf-8")
        else:
            logger.warning("Unsupported file format %s — skipping %s", suffix, path)
            return None
    except Exception:
        logger.error("Failed to read %s", path, exc_info=True)
        return None


def ingest(file_paths: list[str]) -> int:
    """Chunk, embed, and store all files. Returns total number of chunks stored."""
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


