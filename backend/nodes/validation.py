from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from graph.state import CourseState
from schemas.validation import ValidationOutput
from utils.logging import get_logger

logger = get_logger(__name__)

# gpt-4o-mini pricing (USD per token)
INPUT_COST_PER_TOKEN  = 0.15  / 1_000_000
OUTPUT_COST_PER_TOKEN = 0.60  / 1_000_000

# Estimated OUTPUT tokens per content item per session
_CONTENT_OUTPUT = {
    "lesson":       2_000,
    "video_script": 3_000,
    "quiz":         1_000,
    "worksheet":    1_500,
}

# Fixed OUTPUT token budgets for non-content pipeline stages
_PREPROCESSING_PER_DOC   = 600   # extraction + merge per uploaded file
_VALIDATION_OUTPUT        = 300   # feasibility report
_GAP_ENRICHMENT_OUTPUT    = 400   # per gap (rough average: assume 2 gaps)
_CURRICULUM_PLAN_OUTPUT   = 150   # per session (schedule + objectives)
_CRITIC_OUTPUT            = 100   # per session (review pass)

SYSTEM_PROMPT = """You are a curriculum validation expert reviewing course briefs submitted by tutors.

Assess the following three dimensions and produce a structured report:

1. AGE APPROPRIATENESS
   - Is the subject and difficulty level suitable for the stated audience age?
   - Flag a clear mismatch (e.g. advanced calculus for 7-year-olds).
   - Suggest adjustments if the level is borderline.

2. DURATION FEASIBILITY
   - Can the subject realistically be covered at the stated level across the given number of sessions?
   - Flag if the scope is too ambitious or too thin for the schedule.

3. KNOWLEDGE BASE DEPTH
   - Based on uploaded file count and any additional context, is there enough source material for the full course?
   - Flag if the knowledge base looks thin relative to the scope.

Rules:
- flags: blocking issues the tutor must see before anything proceeds
- suggestions: non-blocking improvements or things worth considering
- Never silently omit or soften a flag — surface everything
- Be specific, not generic
"""


_llm = None
_validator = None


def _get_validator():
    global _llm, _validator
    if _llm is None:
        _llm = init_chat_model(model="gpt-4o-mini", temperature=0.3)
        _validator = _llm.with_structured_output(ValidationOutput)
    return _validator


def _estimate_cost(state: dict) -> float:
    """Estimate total pipeline cost in USD across all stages.

    Covers: preprocessing, validation, gap enrichment, curriculum planning,
    content generation, and critic review.  Uses gpt-4o-mini output pricing
    as the dominant cost driver; input tokens are included at their rate.
    """
    sessions_total: int = state.get("sessions_total", 0)
    formats: list[str] = state.get("preferred_formats", [])
    n_docs: int = len(state.get("uploaded_files", []))
    n_urls: int = len(state.get("enrichment_urls", []))
    n_gaps: int = 2  # conservative average; flagged gaps often number 1-3

    output_tokens = 0

    # Preprocessing: one extraction call per file/URL + one merge call
    output_tokens += (n_docs + n_urls) * _PREPROCESSING_PER_DOC
    if n_docs + n_urls > 0:
        output_tokens += _PREPROCESSING_PER_DOC  # merge call

    # Validation
    output_tokens += _VALIDATION_OUTPUT

    # Gap enrichment (runs only when gaps exist — include as expected cost)
    output_tokens += n_gaps * _GAP_ENRICHMENT_OUTPUT

    # Curriculum planning
    output_tokens += sessions_total * _CURRICULUM_PLAN_OUTPUT

    # Content generation per session
    content_per_session = sum(_CONTENT_OUTPUT.get(f, 1_500) for f in formats)
    output_tokens += sessions_total * content_per_session

    # Critic review
    output_tokens += sessions_total * _CRITIC_OUTPUT

    return round(output_tokens * OUTPUT_COST_PER_TOKEN, 4)


async def validation_agent(state: CourseState) -> dict:
    validator = _get_validator()

    brief = f"""Course Brief:
- Subject: {state['subject']}
- Audience Age: {state['audience_age']}
- Audience Level: {state['audience_level']}
- Duration: {state['duration_weeks']} weeks, {state['sessions_per_week']} sessions/week ({state['sessions_total']} sessions total)
- Content Formats: {', '.join(state['preferred_formats'])}
- Tone: {state['tone']}
- Uploaded Files: {len(state.get('uploaded_files', []))} file(s)
- Additional Context: {state.get('additional_context') or 'None provided'}
"""

    logger.info("Running feasibility check for: %s", state["subject"])
    result = await validator.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=brief),
    ])

    estimated_cost = _estimate_cost(state)
    logger.info("Estimated cost: $%.4f | Flags: %d | Suggestions: %d", estimated_cost, len(result.flags), len(result.suggestions))
    if result.flags:
        for flag in result.flags:
            logger.warning("FLAG: %s", flag)

    feasibility_report = {
        "age_appropriateness": {
            "ok": result.age_appropriateness_ok,
            "note": result.age_appropriateness_note,
        },
        "duration_feasibility": {
            "ok": result.duration_feasibility_ok,
            "note": result.duration_feasibility_note,
        },
        "knowledge_base": {
            "ok": result.knowledge_base_ok,
            "note": result.knowledge_base_note,
        },
    }

    logger.info("Awaiting tutor approval at HITL checkpoint")
    verdict = interrupt({
        "feasibility_report": feasibility_report,
        "flags": result.flags,
        "suggestions": result.suggestions,
        "estimated_cost_usd": estimated_cost,
    })

    logger.info("Tutor verdict: %s", "approved" if verdict["approved"] else "revision requested")
    return {
        "feasibility_report": feasibility_report,
        "flags": result.flags,
        "suggestions": result.suggestions,
        "estimated_cost_usd": estimated_cost,
        "user_approved": verdict["approved"],
    }
