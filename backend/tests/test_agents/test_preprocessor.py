import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pypdf import PdfWriter

from agents.preprocessor import knowledge_base_preprocessor
from schemas.preprocessor import DocumentExtraction, KnowledgeSummary

MINIMAL_STATE = {
    "subject": "Python Programming",
    "audience_age": "16-18 years",
    "audience_level": "beginner",
    "duration_weeks": 4,
    "sessions_per_week": 2,
    "sessions_total": 8,
    "preferred_formats": ["lesson", "quiz"],
    "tone": "encouraging",
    "uploaded_files": [],
    "enrichment_urls": [],
    "additional_context": "",
}

SAMPLE_EXTRACTION = DocumentExtraction(
    content_summary="Introduces Python variables and loops, explaining how variables store data and how for/while loops repeat actions.",
    topics=["variables", "loops"],
    depth="introductory",
    subtopics=["for loops", "while loops"],
    teaching_minutes=60,
    prerequisites=["basic computer literacy"],
    gaps=["functions", "classes"],
)

SAMPLE_SUMMARY = KnowledgeSummary(
    content_overview="The knowledge base covers Python fundamentals — variables and loop constructs — with clear explanations suitable for beginners.",
    total_topics=["variables", "loops"],
    coverage_depth="introductory",
    total_teaching_minutes=60,
    prerequisites=["basic computer literacy"],
    gaps=["functions", "classes"],
    fit_for_audience="Good fit for beginner 16-18 year olds.",
    fit_for_duration="Content covers roughly 2 sessions; more material recommended.",
    recommendations=["Add a module on functions and classes."],
)


@pytest.fixture
def sample_txt(tmp_path: Path) -> str:
    f = tmp_path / "notes.txt"
    f.write_text(
        "Introduction to Python\n\nVariables store data. "
        "Loops repeat actions. For loops iterate over sequences. "
        "While loops run until a condition is false.",
        encoding="utf-8",
    )
    return str(f)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> str:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_path = tmp_path / "slides.pdf"
    pdf_path.write_bytes(buf.getvalue())
    return str(pdf_path)


def _mock_models(extraction=SAMPLE_EXTRACTION, summary=SAMPLE_SUMMARY):
    mock_extractor = MagicMock()
    mock_extractor.invoke.return_value = extraction
    mock_merger = MagicMock()
    mock_merger.invoke.return_value = summary
    return mock_extractor, mock_merger


@pytest.mark.anyio
async def test_preprocessor_populates_knowledge_summary(sample_txt, sample_pdf):
    extractor, merger = _mock_models()
    state = {**MINIMAL_STATE, "uploaded_files": [sample_txt, sample_pdf]}

    with patch("agents.preprocessor._get_models", return_value=(extractor, merger)), \
         patch("agents.preprocessor.ingest", return_value=5) as mock_ingest, \
         patch("agents.preprocessor.ingest_texts", return_value=0):
        result = await knowledge_base_preprocessor(state)

    assert "knowledge_summary" in result
    assert result["knowledge_base_ingested"] is True
    summary = result["knowledge_summary"]
    assert isinstance(summary, dict)
    for field in KnowledgeSummary.model_fields:
        assert field in summary, f"Missing field: {field}"
    assert summary["total_topics"] == ["variables", "loops"]
    mock_ingest.assert_called_once_with([sample_txt, sample_pdf])


@pytest.mark.anyio
async def test_preprocessor_skips_unreadable_file(sample_txt):
    extractor, merger = _mock_models()
    state = {
        **MINIMAL_STATE,
        "uploaded_files": ["/nonexistent/file.txt", sample_txt],
    }

    with patch("agents.preprocessor._get_models", return_value=(extractor, merger)), \
         patch("agents.preprocessor.ingest", return_value=3), \
         patch("agents.preprocessor.ingest_texts", return_value=0):
        result = await knowledge_base_preprocessor(state)

    assert "knowledge_summary" in result
    assert result["knowledge_base_ingested"] is True


@pytest.mark.anyio
async def test_preprocessor_raises_when_all_files_fail():
    extractor, merger = _mock_models()
    state = {**MINIMAL_STATE, "uploaded_files": ["/bad/path1.txt", "/bad/path2.pdf"]}

    with patch("agents.preprocessor._get_models", return_value=(extractor, merger)), \
         patch("agents.preprocessor.ingest", return_value=0), \
         patch("agents.preprocessor.ingest_texts", return_value=0):
        with pytest.raises(RuntimeError, match="No content could be successfully extracted"):
            await knowledge_base_preprocessor(state)
