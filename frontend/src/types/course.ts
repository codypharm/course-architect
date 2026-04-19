export interface QuizQuestion {
  question: string
  options: string[]
  answer: string
  explanation: string
}

export interface SessionPlan {
  week: number
  session: number
  topic: string
  objectives: string[]
  lesson_outline: string[]
  quiz_questions: QuizQuestion[]
}

export interface CurriculumPlan {
  course_overview: string
  sessions: SessionPlan[]
}

export interface CourseData {
  thread_id: string
  status: string
  data: {
    curriculum_plan?: CurriculumPlan
    session_content?: SessionPlan[]
  }
}

export type CourseStatus = 'queued' | 'processing' | 'awaiting_validation' | 'awaiting_curriculum_review' | 'completed' | 'rejected' | 'failed'

export interface CourseListItem {
  thread_id: string
  subject: string
  status: CourseStatus
  created_at: string
  updated_at: string
}
