from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question."""
    question: str    = Field(description="The question text.")
    options:  list[str] = Field(description="Exactly 4 answer options (A–D).")
    answer:   str    = Field(description="The correct option — must match one of the options verbatim.")
    explanation: str = Field(description="One or two sentences explaining why the answer is correct.")


class SessionPlan(BaseModel):
    """Full generated content for one teaching session.

    Format fields (lesson_content, video_script, quiz_questions, worksheet_exercises) are
    conditionally populated based on the course's preferred_formats list.
    Leave a field as its default (empty string / empty list) when its format was not selected.
    """
    week:    int = Field(description="Week number (1-based).")
    session: int = Field(description="Session number within the week (1-based).")
    topic:   str = Field(description="Specific topic covered in this session.")

    objectives: list[str] = Field(
        description=(
            "2–4 measurable learning objectives. Always populate regardless of formats selected. "
            "Each objective should be a complete sentence starting with an action verb (e.g. 'Explain...', 'Apply...', 'Compare...')."
        )
    )

    lesson_outline: list[str] = Field(
        default=[],
        description=(
            "4–8 brief ordered teaching points summarising the lesson flow. "
            "Always populate — used for the curriculum review overview regardless of lesson format selection."
        )
    )

    lesson_content: str = Field(
        default="",
        description=(
            "ONLY populate when 'lesson' is in preferred_formats. "
            "A complete, ready-to-teach prose lesson (400–700 words) the tutor reads from. "
            "Structure it as five clearly labelled sections:\n"
            "  1. Introduction — hook the learner, explain why this topic matters, link to prior knowledge\n"
            "  2. Core Concepts — explain each key idea in plain language with concrete, age-appropriate examples\n"
            "  3. Deeper Exploration — nuances, common misconceptions, real-world applications\n"
            "  4. Guided Questions — 2–3 open questions for class discussion or personal reflection\n"
            "  5. Summary — recap the main takeaways in 2–3 sentences\n"
            "Write in full prose paragraphs, not bullet points."
        )
    )

    video_script: str = Field(
        default="",
        description=(
            "ONLY populate when 'video_script' is in preferred_formats. "
            "A complete narration script (300–500 words, ~3 min) the tutor records. "
            "Structure it as five sections:\n"
            "  1. Intro — surprising hook (fact, question, or story), then state topic and learning outcomes\n"
            "  2. Learning Objectives — read each objective aloud in natural conversational language\n"
            "  3. Body — explain every key concept as natural spoken prose with examples and analogies\n"
            "  4. Summary — recap the 3 most important points\n"
            "  5. Call to Action — tell the viewer exactly what to do next\n"
            "Write as continuous spoken prose with natural transitions — not bullet points."
        )
    )

    quiz_questions: list[QuizQuestion] = Field(
        default=[],
        description=(
            "ONLY populate when 'quiz' is in preferred_formats. "
            "2–4 multiple-choice questions testing the session's learning objectives. "
            "Each question must have exactly 4 options and one unambiguously correct answer."
        )
    )

    worksheet_exercises: list[str] = Field(
        default=[],
        description=(
            "ONLY populate when 'worksheet' is in preferred_formats. "
            "4–6 self-contained practice exercises the learner completes independently. "
            "Mix question types: written short-answer, applied problems, or reflection prompts. "
            "Write each as a complete sentence."
        )
    )


class CurriculumPlan(BaseModel):
    """Complete course curriculum and content plan."""
    course_overview: str = Field(
        description=(
            "One paragraph (3–5 sentences) describing the arc of the full course: "
            "what learners will cover, how topics build on each other, and what they will be able to do by the end."
        )
    )
    sessions: list[SessionPlan] = Field(
        description="One SessionPlan per session. Must contain exactly the number of sessions specified in the prompt."
    )
