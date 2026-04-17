from pydantic import BaseModel


class DocumentExtraction(BaseModel):
    content_summary: str        # prose summary of what the document actually teaches
    topics: list[str]
    depth: str                  # "introductory" | "intermediate" | "advanced"
    subtopics: list[str]
    teaching_minutes: int
    prerequisites: list[str]
    gaps: list[str]


class KnowledgeSummary(BaseModel):
    content_overview: str       # synthesised prose summary of all documents combined
    total_topics: list[str]
    coverage_depth: str         # "introductory" | "intermediate" | "advanced" | "mixed"
    total_teaching_minutes: int
    prerequisites: list[str]
    gaps: list[str]
    fit_for_audience: str
    fit_for_duration: str
    recommendations: list[str]
