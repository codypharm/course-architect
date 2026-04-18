export type CourseStatus =
  | 'queued'
  | 'processing'
  | 'awaiting_validation'
  | 'awaiting_curriculum_review'
  | 'completed'
  | 'rejected'
  | 'failed'

export interface CourseStatusResponse {
  thread_id: string
  status: CourseStatus
  data: Record<string, unknown>
}

export interface CourseListItem {
  thread_id: string
  subject: string
  status: CourseStatus
  created_at: string
  updated_at: string
  curriculum_plan: Record<string, unknown> | null
  session_content: unknown[] | null
}

export interface FileUploadResponse {
  file_id: string
  filename: string
  path: string
  size_bytes: number
}
