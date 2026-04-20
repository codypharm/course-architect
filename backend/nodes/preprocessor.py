"""Knowledge base preprocessor node.

Reads all uploaded files and fetches all tutor-provided URLs, extracts a unified
KnowledgeSummary across all sources, and chunks + embeds everything into the vector
store so every downstream agent can call retrieve() freely.
"""
import asyncio
import json

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from graph.state import CourseState
from utils.fetchers import fetch_url, fetch_youtube, is_youtube
from rag.ingest import ingest, ingest_texts, _read_file as _read_file_from_store
from schemas.preprocessor import DocumentExtraction, KnowledgeSummary
from utils.logging import get_logger

logger = get_logger(__name__)

EXTRACTION_PROMPT = """You are analysing a document to extract structured information for course planning.

Given the document content below, extract:
- content_summary: a clear prose summary of what this document actually teaches — the key knowledge, concepts, and explanations it contains
- topics: the main topics covered
- depth: difficulty level of the content — one of "introductory", "intermediate", or "advanced"
- subtopics: specific subtopics or concepts covered
- teaching_minutes: estimated teaching time in minutes to cover this content
- prerequisites: prior knowledge a student needs to understand this document
- gaps: important related topics that appear missing or underdeveloped in this document

Document content:
{document_content}"""

MERGE_PROMPT = """You are synthesising multiple document analyses into a unified knowledge base summary for course planning.

Course context:
- Subject: {subject}
- Audience Age: {audience_age}
- Audience Level: {audience_level}
- Duration: {duration_weeks} weeks, {sessions_per_week} sessions/week
- Documents analysed: {file_count}

Individual document analyses:
{extractions_json}

Produce a single unified summary:
- content_overview: a clear prose synthesis of the actual knowledge across all documents — what concepts, explanations, and material are available for generating the course
- total_topics: all unique topics covered across all documents
- coverage_depth: overall depth — one of "introductory", "intermediate", "advanced", or "mixed"
- total_teaching_minutes: total estimated teaching time across all content
- prerequisites: consolidated prerequisites across all documents
- gaps: topics missing or thin relative to the subject and course duration
- fit_for_audience: assessment of whether the content suits the audience age and level
- fit_for_duration: assessment of whether the content volume matches the course schedule
- recommendations: specific suggestions for improving the knowledge base before generation"""


_llm = None
_extractor = None
_merger = None


def _get_models():
    """Lazily initialise LLM and structured output variants on first call."""
    global _llm, _extractor, _merger
    if _llm is None:
        _llm = init_chat_model(model="gpt-4o-mini", temperature=0.2)
        _extractor = _llm.with_structured_output(DocumentExtraction)
        _merger = _llm.with_structured_output(KnowledgeSummary)
    return _extractor, _merger


async def _fetch_urls(urls: list[str]) -> list[tuple[str, str]]:
    """Fetch all URLs concurrently via asyncio.gather. Returns (content, url) pairs for successful fetches only."""
    async def _fetch_one(url: str) -> tuple[str, str | None]:
        content = await fetch_youtube(url) if is_youtube(url) else await fetch_url(url)
        if content is None:
            logger.warning("Failed to fetch URL — skipping: %s", url)
        return url, content

    pairs = await asyncio.gather(*[_fetch_one(url) for url in urls])
    return [(content, url) for url, content in pairs if content]


def _read_file(path: str) -> str | None:
    """Read a file from S3 (key starting with 'uploads/') or local disk.

    Delegates to rag.ingest._read_file which handles both S3 keys and local
    paths so all file access goes through a single code path.
    """
    return _read_file_from_store(path)


def _extract(content: str, extractor) -> DocumentExtraction | None:
    """Run a single LLM extraction call on document text. Returns None on failure."""
    try:
        return extractor.invoke([HumanMessage(content=EXTRACTION_PROMPT.format(document_content=content))])
    except Exception:
        logger.error("Extraction LLM call failed", exc_info=True)
        return None


def _merge(extractions: list[DocumentExtraction], state: CourseState, merger) -> KnowledgeSummary:
    """Merge all per-document extractions into a single KnowledgeSummary via LLM. Raises on failure."""
    extractions_json = json.dumps([e.model_dump() for e in extractions], indent=2)
    try:
        return merger.invoke([
            HumanMessage(content=MERGE_PROMPT.format(
                file_count=len(extractions),
                extractions_json=extractions_json,
                subject=state["subject"],
                audience_age=state["audience_age"],
                audience_level=state["audience_level"],
                duration_weeks=state["duration_weeks"],
                sessions_per_week=state["sessions_per_week"],
            ))
        ])
    except Exception as e:
        raise RuntimeError(
            f"Merge LLM call failed after successfully extracting {len(extractions)} source(s): {e}"
        ) from e


async def knowledge_base_preprocessor(state: CourseState) -> dict:
    """LangGraph node. Reads all uploaded files and fetches all tutor-provided URLs,
    extracts a unified KnowledgeSummary across all sources, and chunks + embeds
    everything into the vector store so every downstream agent can call retrieve() freely."""
    extractor, merger = _get_models()

    # Fetch URLs concurrently while files are read below
    url_contents = await _fetch_urls(state.get("enrichment_urls", []))

    extractions = []

    for path in state.get("uploaded_files", []):
        content = _read_file(path)
        if content is None:
            continue
        extraction = _extract(content, extractor)
        if extraction is None:
            continue
        extractions.append(extraction)

    for content, url in url_contents:
        extraction = _extract(content, extractor)
        if extraction is None:
            continue
        extractions.append(extraction)

    if not extractions:
        # Knowledge base is optional — proceed with subject-only context.
        # Validation agent will flag missing material in the feasibility report.
        logger.warning(
            "No knowledge base content extracted (no files or URLs provided). "
            "Proceeding with subject-only context for thread_id=%s",
            state.get("thread_id", "unknown"),
        )
        return {
            "knowledge_summary": {
                "content_summary": "",
                "topics": [],
                "depth": "introductory",
                "subtopics": [],
                "teaching_minutes": 0,
                "prerequisites": [],
                "gaps": ["No knowledge base provided — content will be generated from subject brief alone."],
                "source_count": 0,
            }
        }

    summary = _merge(extractions, state, merger)

    file_chunks = ingest(state.get("uploaded_files", []))
    url_chunks = ingest_texts(url_contents)
    logger.info("Vector store populated with %d file chunks and %d URL chunks", file_chunks, url_chunks)

    return {"knowledge_summary": summary.model_dump()}
