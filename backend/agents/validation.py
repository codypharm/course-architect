from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from graph.state import CourseState
from schemas.validation import ValidationOutput
from utils.logging import get_logger

logger = get_logger(__name__)

TOKEN_ESTIMATES = {
    "lesson": 2000,
    "video_script": 3000,
    "quiz": 1000,
    "worksheet": 1500,
}
COST_PER_TOKEN = 0.6 / 1_000_000  # gpt-4o-mini output pricing per token

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


def _estimate_cost(sessions_total: int, preferred_formats: list[str]) -> float:
    tokens_per_session = sum(TOKEN_ESTIMATES.get(f, 1500) for f in preferred_formats)
    total_tokens = sessions_total * tokens_per_session
    return round(total_tokens * COST_PER_TOKEN, 4)


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

    estimated_cost = _estimate_cost(state["sessions_total"], state["preferred_formats"])
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
        "user_revisions": verdict.get("revisions", ""),
    }
