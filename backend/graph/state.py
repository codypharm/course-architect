from typing_extensions import TypedDict


class CourseState(TypedDict):
    # Form submission
    subject: str
    audience_age: str
    audience_level: str
    duration_weeks: int
    sessions_per_week: int
    sessions_total: int
    preferred_formats: list[str]          # ["lesson", "video_script", "quiz", "worksheet"]
    tone: str                             # e.g. "formal", "casual", "encouraging", "socratic"
    uploaded_files: list[str]
    additional_context: str               # any extra info the tutor wants factored into generation

    # Validation
    feasibility_report: dict
    flags: list[str]
    suggestions: list[str]
    estimated_cost_usd: float

    # Human verdict
    user_approved: bool
    user_revisions: str

    # Preprocessor
    knowledge_summary: dict               # serialised KnowledgeSummary from preprocessor node
    knowledge_base_ingested: bool         # True once rag_ingest_node has run

    # Enrichment
    enriched_knowledge_base: str

    # Generation
    curriculum_plan: dict                 # {week: int, session: int, topic: str, objectives: list}
    session_content: list[dict]           # per-session output objects

    # Review
    critic_feedback: dict
    critic_approved: bool

    # Retry
    retry_count: int                      # starts at 0, max 5
    retry_context: str                    # tutor's refinement instruction, empty string if none
    retry_history: list[dict]             # [{retry_count, retry_context, timestamp}]
