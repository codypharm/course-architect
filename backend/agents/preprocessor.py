import json
import logging
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from graph.state import CourseState
from schemas.preprocessor import DocumentExtraction, KnowledgeSummary

logger = logging.getLogger(__name__)

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


def _read_file(path: str) -> str | None:
    """Read a PDF, txt, or md file and return its text content. Returns None on any failure."""
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
            logger.warning("Unsupported file format %s for %s", suffix, path)
            return None
    except Exception:
        logger.error("Failed to read file %s", path, exc_info=True)
        return None


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
            f"Merge LLM call failed after successfully extracting {len(extractions)} file(s): {e}"
        ) from e


def knowledge_base_preprocessor(state: CourseState) -> dict:
    """LangGraph node. Reads all uploaded files, extracts structured knowledge from each,
    and merges them into a unified KnowledgeSummary written to state['knowledge_summary']."""
    extractor, merger = _get_models()

    extractions = []
    for path in state.get("uploaded_files", []):
        content = _read_file(path)
        if content is None:
            continue
        extraction = _extract(content, extractor)
        if extraction is None:
            continue
        extractions.append(extraction)

    if not extractions:
        raise RuntimeError(
            "No files could be successfully extracted from the knowledge base. "
            "Check that uploaded_files contains valid paths to PDF, txt, or md files."
        )

    summary = _merge(extractions, state, merger)
    return {"knowledge_summary": summary.model_dump()}
