import { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth, UserButton } from '@clerk/clerk-react'
import { api } from '@/lib/api'
import type { CourseListItem, CourseStatus } from '@/types/course'
import { Ico, I } from '@/components/Icon'
import NewCourseForm, { type CourseBrief } from '@/components/NewCourseForm'
import PipelineTracker from '@/components/PipelineTracker'

/* ─── API ─── */
async function fetchCourses(userId: string): Promise<CourseListItem[]> {
  const res = await api.get<CourseListItem[]>(`/users/${userId}/courses`)
  return res.data
}

interface QuizQuestion { question: string; options: string[]; answer: string; explanation: string }
interface SessionPlan  { week: number; session: number; topic: string; objectives: string[]; lesson_outline: string[]; lesson_content: string; video_script: string; quiz_questions: QuizQuestion[]; worksheet_exercises: string[] }
interface CurriculumPlan { course_overview: string; sessions: SessionPlan[] }
interface CourseDetail { thread_id: string; status: string; data: { curriculum_plan?: CurriculumPlan; session_content?: SessionPlan[] } }

async function fetchCourseDetail(threadId: string): Promise<CourseDetail> {
  const res = await api.get<CourseDetail>(`/courses/${threadId}`)
  return res.data
}

/* ─── Status helpers ─── */
const STATUS_BADGE: Record<CourseStatus, { label: string; bg: string; color: string; live?: boolean }> = {
  queued:                     { label: 'Queued',              bg: '#F7F6F3',                color: 'var(--ink-muted)' },
  processing:                 { label: 'Processing',          bg: '#F7F6F3',                color: 'var(--ink-muted)',          live: true },
  awaiting_validation:        { label: 'Awaiting Validation', bg: 'var(--accent-yellow-bg)',color: 'var(--accent-yellow-text)', live: true },
  awaiting_curriculum_review: { label: 'Review Curriculum',   bg: 'var(--accent-yellow-bg)',color: 'var(--accent-yellow-text)', live: true },
  completed:                  { label: 'Complete',            bg: 'var(--accent-green-bg)', color: 'var(--accent-green-text)' },
  rejected:                   { label: 'Rejected',            bg: 'var(--accent-red-bg)',   color: 'var(--accent-red-text)' },
  failed:                     { label: 'Failed',              bg: 'var(--accent-red-bg)',   color: 'var(--accent-red-text)' },
}

function isActive(s: CourseStatus) {
  return s === 'queued' || s === 'processing' || s === 'awaiting_validation' || s === 'awaiting_curriculum_review'
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

/* ─── Badge ─── */
function Badge({ status }: { status: CourseStatus }) {
  const b = STATUS_BADGE[status]
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', padding: '3px 9px', borderRadius: 9999, background: b.bg, color: b.color, whiteSpace: 'nowrap' }}>
      {b.live && <span style={{ width: 5, height: 5, borderRadius: '50%', background: b.color, display: 'inline-block', animation: 'pulse 1.2s ease infinite' }} />}
      {b.label}
    </span>
  )
}

/* ─── Thumb ─── */
function Thumb({ subject }: { subject: string }) {
  const paths = [I.book, I.layers, I.settings, I.grid]
  return (
    <div style={{ width: 42, height: 42, borderRadius: 8, background: '#F7F6F3', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <Ico d={paths[subject.length % paths.length]} size={19} color="var(--ink-muted)" />
    </div>
  )
}

/* ─── Active card ─── */
function ActiveCard({ course }: { course: CourseListItem }) {
  const processing = course.status === 'processing'
  const actionable = course.status === 'awaiting_validation' || course.status === 'awaiting_curriculum_review'
  return (
    <Link to={`/courses/${course.thread_id}`} style={{ display: 'block', textDecoration: 'none', background: '#fff', border: '1px solid var(--border)', borderRadius: 10, padding: '18px', transition: 'box-shadow 200ms' }}
      onMouseEnter={e => (e.currentTarget as HTMLElement).style.boxShadow = '0 2px 8px rgba(0,0,0,0.05)'}
      onMouseLeave={e => (e.currentTarget as HTMLElement).style.boxShadow = 'none'}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <Thumb subject={course.subject} />
        <Badge status={course.status} />
      </div>
      <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)', margin: '0 0 5px', lineHeight: 1.3 }}>{course.subject}</h3>
      <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 14px', lineHeight: 1.5 }}>
        {actionable
          ? course.status === 'awaiting_validation'
            ? 'Validation complete — review the pre-flight report to proceed.'
            : 'Curriculum plan ready — approve to generate full content.'
          : processing ? 'AI is generating your course content.'
          : 'Queued for processing.'}
      </p>
      {processing && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ height: 4, borderRadius: 2, background: '#EAEAEA', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: '65%', borderRadius: 2, background: 'var(--ink)', animation: 'indeterminate 2s ease-in-out infinite alternate' }} />
          </div>
          <p style={{ fontSize: 11, color: 'var(--ink-faint)', textAlign: 'right', margin: '4px 0 0' }}>In progress</p>
        </div>
      )}
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10, fontSize: 11, color: 'var(--ink-faint)', display: 'flex', alignItems: 'center', gap: 5 }}>
        <Ico d={I.calendar} size={11} color="var(--ink-faint)" /> Updated {timeAgo(course.updated_at)}
      </div>
    </Link>
  )
}

/* ─── Completed row ─── */
function CompletedRow({ course, onDelete }: { course: CourseListItem; onDelete: () => void }) {
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    if (!window.confirm(`Delete "${course.subject}"? This cannot be undone.`)) return
    setDeleting(true)
    try {
      await api.delete(`/courses/${course.thread_id}`)
      onDelete()
    } catch {
      alert('Failed to delete course. Please try again.')
      setDeleting(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
      <Thumb subject={course.subject} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', margin: '0 0 1px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{course.subject}</p>
        <p style={{ fontSize: 11, color: 'var(--ink-faint)', margin: 0 }}>Completed {timeAgo(course.updated_at)}</p>
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <Link to={`/courses/${course.thread_id}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 500, color: 'var(--ink)', textDecoration: 'none', padding: '5px 10px', border: '1px solid var(--border)', borderRadius: 6, background: '#fff' }}>
          <Ico d={I.eye} size={12} color="var(--ink)" /> View
        </Link>
        <button
          onClick={handleDelete}
          disabled={deleting}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 500, color: deleting ? 'var(--ink-faint)' : 'var(--accent-red-text)', padding: '5px 10px', border: `1px solid ${deleting ? 'var(--border)' : 'var(--accent-red-text)'}`, borderRadius: 6, background: '#fff', cursor: deleting ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)', opacity: deleting ? 0.6 : 1 }}
        >
          <Ico d={I.trash} size={12} color={deleting ? 'var(--ink-faint)' : 'var(--accent-red-text)'} />
          {deleting ? 'Deleting…' : 'Delete'}
        </button>
      </div>
    </div>
  )
}

/* ─── Quiz card ─── */
function QuizCard({ q, idx }: { q: QuizQuestion; idx: number }) {
  const [revealed, setRevealed] = useState(false)
  return (
    <div style={{ background: '#F7F6F3', borderRadius: 10, padding: '14px 16px', marginBottom: 8 }}>
      <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', margin: '0 0 10px', lineHeight: 1.4 }}>Q{idx + 1}. {q.question}</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 10 }}>
        {q.options.map((opt, i) => {
          const correct = revealed && opt === q.answer
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 7, border: `1px solid ${correct ? 'var(--accent-green-text)' : 'var(--border)'}`, background: correct ? 'var(--accent-green-bg)' : '#fff', transition: 'all 200ms' }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: correct ? 'var(--accent-green-text)' : 'var(--ink-muted)', minWidth: 16 }}>{['A','B','C','D'][i]}</span>
              <span style={{ fontSize: 13, color: correct ? 'var(--accent-green-text)' : 'var(--ink)' }}>{opt}</span>
            </div>
          )
        })}
      </div>
      {revealed
        ? <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: 0, lineHeight: 1.4, borderTop: '1px solid var(--border)', paddingTop: 8 }}><strong style={{ color: 'var(--ink)' }}>Explanation:</strong> {q.explanation}</p>
        : <button onClick={() => setRevealed(true)} style={{ fontSize: 12, fontWeight: 500, color: 'var(--ink-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: 'var(--font-sans)' }}>Reveal answer →</button>
      }
    </div>
  )
}

type FormatTab = 'lesson' | 'video_script' | 'quiz' | 'worksheet'

const FORMAT_TAB_LABELS: Record<FormatTab, string> = {
  lesson:       'Lesson',
  video_script: 'Video Script',
  quiz:         'Quiz',
  worksheet:    'Worksheet',
}

/** Returns the format tabs that have actual content for this session. */
function activeFormatTabs(s: SessionPlan): FormatTab[] {
  const tabs: FormatTab[] = []
  if (s.lesson_content?.trim() || s.lesson_outline?.length) tabs.push('lesson')
  if (s.video_script?.trim())                               tabs.push('video_script')
  if (s.quiz_questions?.length)                             tabs.push('quiz')
  if (s.worksheet_exercises?.length)                        tabs.push('worksheet')
  return tabs
}

import { Markdown } from '@/components/Markdown'

/* ─── Session format tab content ─── */
function SessionFormatContent({ session, tab }: { session: SessionPlan; tab: FormatTab }) {
  if (tab === 'lesson') return (
    <div>
      {session.lesson_content?.trim() ? (
        <div style={{ padding: '0 4px', maxWidth: 720 }}>
          <Markdown content={session.lesson_content} />
        </div>
      ) : session.lesson_outline?.length ? (
        <ol style={{ margin: 0, padding: '0 0 0 20px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {session.lesson_outline.map((pt, i) => (
            <li key={i} style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.6 }}>{pt}</li>
          ))}
        </ol>
      ) : null}
    </div>
  )

  if (tab === 'video_script') return (
    <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 24px', maxWidth: 720 }}>
      <Markdown content={session.video_script} />
    </div>
  )

  if (tab === 'quiz') return (
    <div>
      {session.quiz_questions.map((q, i) => <QuizCard key={i} q={q} idx={i} />)}
    </div>
  )

  if (tab === 'worksheet') return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {session.worksheet_exercises.map((ex, i) => (
        <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 14px', background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink-muted)', flexShrink: 0, minWidth: 20 }}>{i + 1}.</span>
          <span style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.5 }}>{ex}</span>
        </div>
      ))}
    </div>
  )

  return null
}

/* ─── Course detail view (rendered inside dashboard main area) ─── */
function CourseView({ threadId, onBack }: { threadId: string; onBack: () => void }) {
  const [activeSession, setActiveSession] = useState(0)
  const [activeTab, setActiveTab]         = useState<FormatTab | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['course-detail', threadId],
    queryFn: () => fetchCourseDetail(threadId),
  })

  const plan: CurriculumPlan | null = (data?.data?.curriculum_plan as CurriculumPlan) ?? null
  const sessions: SessionPlan[] = plan?.sessions ?? (data?.data?.session_content as SessionPlan[]) ?? []

  const byWeek: Record<number, SessionPlan[]> = {}
  sessions.forEach(s => { if (!byWeek[s.week]) byWeek[s.week] = []; byWeek[s.week].push(s) })

  const current = sessions[activeSession] ?? null

  if (isLoading) return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 8 }}>
      {[200, 140, 180, 120].map((w, i) => <div key={i} style={{ height: 16, width: w, background: '#EAEAEA', borderRadius: 4 }} />)}
    </div>
  )

  if (isError) return (
    <div style={{ padding: '32px 0', textAlign: 'center' }}>
      <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: 0 }}>Could not load course content.</p>
    </div>
  )

  return (
    <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
      {/* Session sidebar */}
      <aside style={{ width: 220, flexShrink: 0, background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '10px 0', position: 'sticky', top: 16, maxHeight: 'calc(100vh - 120px)', overflowY: 'auto' }}>
        {/* Back to overview */}
        <button onClick={() => setActiveSession(-1)} style={{ width: '100%', textAlign: 'left', padding: '8px 14px', background: activeSession === -1 ? '#F7F6F3' : 'transparent', border: 'none', borderLeft: `3px solid ${activeSession === -1 ? 'var(--ink)' : 'transparent'}`, cursor: 'pointer', fontFamily: 'var(--font-sans)', marginBottom: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>Overview</span>
        </button>
        {Object.entries(byWeek).map(([week, rows]) => (
          <div key={week}>
            <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink-faint)', margin: '8px 14px 3px' }}>Week {week}</p>
            {rows.map(s => {
              const idx = sessions.indexOf(s)
              const on  = activeSession === idx
              return (
                <button key={idx} onClick={() => setActiveSession(idx)} style={{ width: '100%', textAlign: 'left', padding: '6px 14px', background: on ? '#F7F6F3' : 'transparent', border: 'none', borderLeft: `3px solid ${on ? 'var(--ink)' : 'transparent'}`, cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
                  <span style={{ fontSize: 10, color: 'var(--ink-faint)', display: 'block' }}>Session {s.session}</span>
                  <span style={{ fontSize: 12, fontWeight: on ? 600 : 400, color: 'var(--ink)', lineHeight: 1.3, display: 'block' }}>{s.topic}</span>
                </button>
              )
            })}
          </div>
        ))}
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Back button */}
        <button onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--ink-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: 'var(--font-sans)', marginBottom: 16 }}>
          ← Back to dashboard
        </button>

        {/* Overview panel */}
        {(activeSession === -1 || !current) && plan?.course_overview && (
          <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '22px', marginBottom: 16 }}>
            <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: '0 0 8px' }}>Course Overview</p>
            <p style={{ fontSize: 15, color: 'var(--ink)', lineHeight: 1.7, margin: '0 0 16px' }}>{plan.course_overview}</p>
            <div style={{ display: 'flex', gap: 20, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
              {[['Sessions', sessions.length], ['Weeks', Object.keys(byWeek).length], ['Quiz questions', sessions.reduce((a, s) => a + s.quiz_questions.length, 0)]].map(([label, val]) => (
                <div key={label as string}>
                  <p style={{ fontSize: 11, color: 'var(--ink-faint)', margin: '0 0 2px' }}>{label}</p>
                  <p style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)', margin: 0, fontFamily: 'var(--font-mono)' }}>{val}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Session panel */}
        {activeSession >= 0 && current && (() => {
          const tabs = activeFormatTabs(current)
          const resolvedTab = (activeTab && tabs.includes(activeTab)) ? activeTab : (tabs[0] ?? null)
          return (
            <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '22px' }}>
              {/* Header row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                <div>
                  <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: '0 0 4px' }}>Week {current.week} · Session {current.session}</p>
                  <h2 className="serif" style={{ fontSize: 22, color: 'var(--ink)', margin: 0, letterSpacing: '-0.02em' }}>{current.topic}</h2>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={() => { setActiveSession(i => Math.max(0, i - 1)); setActiveTab(null) }} disabled={activeSession === 0}
                    style={{ width: 30, height: 30, borderRadius: 6, border: '1px solid var(--border)', background: '#fff', cursor: activeSession === 0 ? 'default' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: activeSession === 0 ? 0.3 : 1 }}>
                    <span style={{ display: 'inline-flex', transform: 'rotate(180deg)' }}><Ico d={I.arrow} size={12} color="var(--ink)" /></span>
                  </button>
                  <button onClick={() => { setActiveSession(i => Math.min(sessions.length - 1, i + 1)); setActiveTab(null) }} disabled={activeSession === sessions.length - 1}
                    style={{ width: 30, height: 30, borderRadius: 6, border: '1px solid var(--border)', background: '#fff', cursor: activeSession === sessions.length - 1 ? 'default' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: activeSession === sessions.length - 1 ? 0.3 : 1 }}>
                    <Ico d={I.arrow} size={12} color="var(--ink)" />
                  </button>
                </div>
              </div>

              {/* Objectives — always shown above tabs */}
              {current.objectives.length > 0 && (
                <div style={{ marginBottom: 18 }}>
                  <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: '0 0 8px' }}>Learning Objectives</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {current.objectives.map((o, i) => (
                      <div key={i} style={{ display: 'flex', gap: 8, padding: '7px 12px', background: '#F7F6F3', borderRadius: 7 }}>
                        <span style={{ fontSize: 13, color: 'var(--ink-muted)', flexShrink: 0 }}>→</span>
                        <span style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.4 }}>{o}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Format tabs */}
              {tabs.length > 0 && (
                <>
                  <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
                    {tabs.map(t => (
                      <button key={t} onClick={() => setActiveTab(t)} style={{
                        fontSize: 12, fontWeight: resolvedTab === t ? 700 : 500,
                        color: resolvedTab === t ? 'var(--ink)' : 'var(--ink-muted)',
                        background: 'none', border: 'none', borderBottom: `2px solid ${resolvedTab === t ? 'var(--ink)' : 'transparent'}`,
                        padding: '6px 12px', cursor: 'pointer', fontFamily: 'var(--font-sans)',
                        marginBottom: -1, transition: 'all 150ms',
                      }}>
                        {FORMAT_TAB_LABELS[t]}
                      </button>
                    ))}
                  </div>
                  {resolvedTab && <SessionFormatContent session={current} tab={resolvedTab} />}
                </>
              )}
            </div>
          )
        })()}

        {sessions.length === 0 && !isLoading && (
          <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '36px', textAlign: 'center' }}>
            <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: 0 }}>No session content available.</p>
          </div>
        )}
      </div>
    </div>
  )
}

/* ══════════════════════════════════════
   DASHBOARD PAGE
══════════════════════════════════════ */
type NavItem = 'dashboard' | 'new' | 'settings' | 'course'

const NAV_ITEMS: { id: Exclude<NavItem, 'course'>; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: I.grid },
  { id: 'new',       label: 'New Course', icon: I.plus },
  { id: 'settings',  label: 'Settings',   icon: I.settings },
]

export default function DashboardPage() {
  const { threadId }          = useParams<{ threadId: string }>()
  const navigate               = useNavigate()
  const { userId }             = useAuth()
  const [nav, setNav]          = useState<NavItem>(threadId ? 'course' : 'dashboard')
  const [search, setSearch]    = useState('')
  const [formKey, setFormKey]      = useState(0)
  const [initialBrief, setInitialBrief] = useState<CourseBrief | undefined>(undefined)
  const qc = useQueryClient()

  // When navigating to /courses/:threadId, switch to course view
  useEffect(() => {
    if (threadId) setNav('course')
  }, [threadId])

  const { data: courses, isLoading } = useQuery({
    queryKey: ['courses', userId],
    queryFn: () => fetchCourses(userId!),
    enabled: !!userId,
    refetchInterval: q => q.state.data?.some(c => isActive(c.status)) ? 5000 : false,
  })

  const active    = (courses ?? []).filter(c => isActive(c.status))
  const completed = (courses ?? []).filter(c => c.status === 'completed')
  const searched  = search.trim()
    ? (courses ?? []).filter(c => c.subject.toLowerCase().includes(search.toLowerCase()))
    : null

  function handleSuccess(_id: string) {
    qc.invalidateQueries({ queryKey: ['courses', userId] })
  }

  function goToDashboard() {
    setNav('dashboard')
    navigate('/dashboard')
  }

  async function handleRevise(tid: string) {
    try {
      const res = await api.get<CourseBrief & {
        audience_age: string; audience_level: string;
        duration_weeks: number; sessions_per_week: number;
        preferred_formats: string[]; tone: string;
        additional_context: string; enrichment_urls: string[];
        uploaded_file_paths: string[];
      }>(`/courses/${tid}/brief`)
      const d = res.data
      setInitialBrief({
        subject:           d.subject,
        audienceAge:       d.audience_age,
        audienceLevel:     d.audience_level,
        tone:              d.tone.charAt(0).toUpperCase() + d.tone.slice(1),
        durationWeeks:     d.duration_weeks,
        sessionsPerWeek:   d.sessions_per_week,
        formats:           d.preferred_formats,
        enrichmentUrls:    d.enrichment_urls,
        additionalContext: d.additional_context,
        uploadedFilePaths: d.uploaded_file_paths,
      })
    } catch {
      setInitialBrief(undefined)
    }
    setFormKey(k => k + 1)
    setNav('new')
  }

  const Logo = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <rect x="3" y="3" width="7" height="7" rx="1"/>
      <rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/>
      <rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
  )

  return (
    <div className="dash-layout" style={{ background: '#F5F6FA', fontFamily: 'var(--font-sans)' }}>
      <style>{`
        @keyframes pulse{0%,100%{opacity:.4;transform:scale(1)}50%{opacity:1;transform:scale(1.3)}}
        @keyframes indeterminate{0%{transform:translateX(-100%)}100%{transform:translateX(300%)}}
        .dash-main { overflow-x: hidden; }
      `}</style>

      {/* ── Desktop sidebar ── */}
      <aside className="dash-sidebar">
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '18px 18px 24px', textDecoration: 'none' }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: 'var(--ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
            <Logo />
          </div>
          <div>
            <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>Course Architect</p>
            <p style={{ fontSize: 11, color: 'var(--ink-faint)', margin: 0 }}>AI Course Gen</p>
          </div>
        </Link>

        <nav style={{ flex: 1, padding: '0 10px' }}>
          {NAV_ITEMS.map(item => {
            const on = nav === item.id
            return (
              <button key={item.id} onClick={() => { if (item.id === 'new') { setInitialBrief(undefined); setFormKey(k => k + 1) } setNav(item.id); if (item.id === 'dashboard') navigate('/dashboard') }} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '9px 12px', borderRadius: 7, marginBottom: 2, background: on ? '#F7F6F3' : 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', color: on ? 'var(--ink)' : 'var(--ink-muted)', fontWeight: on ? 600 : 400, fontSize: 14, textAlign: 'left', transition: 'background 150ms' }}>
                <Ico d={item.icon} size={15} color={on ? 'var(--ink)' : 'var(--ink-muted)'} />
                {item.label}
                {on && <div style={{ marginLeft: 'auto', width: 3, height: 14, borderRadius: 2, background: 'var(--ink)' }} />}
              </button>
            )
          })}
        </nav>

        <div style={{ padding: '12px 14px 20px' }}>
          <button onClick={() => { setInitialBrief(undefined); setFormKey(k => k + 1); setNav('new') }} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, padding: '11px', borderRadius: 8, background: 'var(--ink)', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-sans)' }}>
            <Ico d={I.plus} size={14} color="#fff" /> Generate Course
          </button>
        </div>
      </aside>

      {/* ── Mobile top bar ── */}
      <div className="dash-mobile-bar" style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 30 }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: 'var(--ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
            <Logo />
          </div>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>Course Architect</span>
        </Link>
        {nav === 'dashboard' && (
          <button onClick={() => setNav('new')} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: '#fff', background: 'var(--ink)', padding: '6px 12px', borderRadius: 5, border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
            <Ico d={I.plus} size={13} color="#fff" /> New
          </button>
        )}
        {nav !== 'dashboard' && (
          <button onClick={goToDashboard} style={{ fontSize: 12, color: 'var(--ink-muted)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>← Back</button>
        )}
      </div>

      {/* ── Main content ── */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '0 24px', height: 58, background: '#fff', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ flex: 1 }}>
            {nav === 'dashboard' && <>
              <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>Welcome back</h1>
              <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: 0 }}>Here is the status of your course portfolio.</p>
            </>}
            {nav === 'new'      && <h1 style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>New Course</h1>}
            {nav === 'settings' && <h1 style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>Settings</h1>}
            {nav === 'course'   && <h1 style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>Course Content</h1>}
          </div>
          {nav === 'dashboard' && <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, background: '#F5F6FA', border: '1px solid var(--border)', borderRadius: 7, padding: '6px 11px' }}>
              <Ico d={I.search} size={13} color="var(--ink-faint)" />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search courses…" style={{ border: 'none', background: 'transparent', fontSize: 13, color: 'var(--ink)', outline: 'none', fontFamily: 'var(--font-sans)', width: 160 }} />
            </div>
            <button style={{ width: 34, height: 34, borderRadius: 7, border: '1px solid var(--border)', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
              <Ico d={I.bell} size={15} color="var(--ink-muted)" />
            </button>
          </>}
          <UserButton />
        </header>

        <main className="dash-content-pad" style={{ flex: 1, padding: '24px', paddingTop: '68px', overflowY: 'auto' }}>
          {/* ── Dashboard ── */}
          {nav === 'dashboard' && (
            <div>
              {searched && (
                <section style={{ marginBottom: 32 }}>
                  <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', margin: '0 0 4px' }}>Search results</h2>
                  <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 14px' }}>{searched.length} match{searched.length !== 1 ? 'es' : ''} for "{search}"</p>
                  <div className="course-grid">{searched.map(c => isActive(c.status) ? <ActiveCard key={c.thread_id} course={c} /> : <CompletedRow key={c.thread_id} course={c} onDelete={() => qc.invalidateQueries({ queryKey: ['courses', userId] })} />)}</div>
                </section>
              )}
              {!searched && <>
                <section style={{ marginBottom: 32 }}>
                  <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', margin: '0 0 3px' }}>Active Projects</h2>
                  <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 14px' }}>Courses currently in the generation pipeline.</p>
                  {isLoading ? (
                    <div className="course-grid">{[1,2].map(i => <div key={i} style={{ height: 170, borderRadius: 10, background: '#EAEAEA' }} />)}</div>
                  ) : active.length === 0 ? (
                    <div style={{ padding: '28px 20px', background: '#fff', border: '1px solid var(--border)', borderRadius: 10, textAlign: 'center' }}>
                      <p style={{ fontSize: 13, color: 'var(--ink-muted)', margin: '0 0 12px' }}>No active courses.</p>
                      <button onClick={() => setNav('new')} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#fff', background: 'var(--ink)', padding: '8px 16px', borderRadius: 5, border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
                        <Ico d={I.plus} size={13} color="#fff" /> Generate a course
                      </button>
                    </div>
                  ) : (
                    <div className="course-grid">{active.map(c => <ActiveCard key={c.thread_id} course={c} />)}</div>
                  )}
                </section>
                {completed.length > 0 && (
                  <section>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
                      <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>Completed Courses</h2>
                      <span style={{ fontSize: 13, color: 'var(--ink-muted)', cursor: 'pointer', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4 }}>View All <Ico d={I.arrow} size={12} color="var(--ink-muted)" /></span>
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 14px' }}>Finalised course packs ready to use.</p>
                    <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 10, padding: '0 18px' }}>
                      {completed.map(c => <CompletedRow key={c.thread_id} course={c} onDelete={() => qc.invalidateQueries({ queryKey: ['courses', userId] })} />)}
                    </div>
                  </section>
                )}
              </>}
            </div>
          )}

          {/* ── New Course ── */}
          {nav === 'new' && <NewCourseForm key={formKey} onCancel={goToDashboard} onSuccess={handleSuccess} onReset={() => { setInitialBrief(undefined); setFormKey(k => k + 1) }} initialValues={initialBrief} onRevise={handleRevise} />}

          {/* ── Settings ── */}
          {nav === 'settings' && <p style={{ fontSize: 14, color: 'var(--ink-muted)', paddingTop: 12 }}>Settings coming soon.</p>}

          {/* ── Course detail ── */}
          {nav === 'course' && threadId && (() => {
            const courseStatus = courses?.find(c => c.thread_id === threadId)?.status
            const isActiveStatus = courseStatus && isActive(courseStatus)
            return isActiveStatus
              ? <PipelineTracker threadId={threadId} onReset={goToDashboard} onRevise={() => handleRevise(threadId)} />
              : <CourseView threadId={threadId} onBack={goToDashboard} />
          })()}
        </main>
      </div>

      {/* ── Mobile bottom nav ── */}
      <nav className="dash-bottom-nav">
        {NAV_ITEMS.map(item => {
          const on = nav === item.id
          return (
            <button key={item.id} onClick={() => { setNav(item.id); if (item.id === 'dashboard') navigate('/dashboard') }} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3, border: 'none', background: 'transparent', cursor: 'pointer', color: on ? 'var(--ink)' : 'var(--ink-faint)', fontFamily: 'var(--font-sans)' }}>
              <Ico d={item.icon} size={18} color={on ? 'var(--ink)' : 'var(--ink-faint)'} />
              <span style={{ fontSize: 10, fontWeight: on ? 600 : 400 }}>{item.label}</span>
            </button>
          )
        })}
      </nav>
    </div>
  )
}
