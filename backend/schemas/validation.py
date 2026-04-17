from pydantic import BaseModel


class ValidationOutput(BaseModel):
    age_appropriateness_ok: bool
    age_appropriateness_note: str
    duration_feasibility_ok: bool
    duration_feasibility_note: str
    knowledge_base_ok: bool
    knowledge_base_note: str
    flags: list[str]
    suggestions: list[str]
