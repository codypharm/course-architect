import { useState, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Ico, I } from './Icon'

const USER_ID = 'demo-user'

/* ─── Types ─── */
interface StartCoursePayload {
  user_id: string
  subject: string
  audience_age: string
  audience_level: string
  duration_weeks: number
  sessions_per_week: number
  sessions_total: number
  preferred_formats: string[]
  tone: string
  include_quiz: boolean
  uploaded_file_paths: string[]
  enrichment_urls: string[]
  additional_context: string
}

interface CourseStatusResponse {
  thread_id: string
  status: string
  data: Record<string, unknown>
}

interface UploadedFile { file_id: string; path: string }

/* ─── API helpers ─── */
async function uploadFiles(files: File[]): Promise<string[]> {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  const res = await api.post<UploadedFile[]>('/files', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  return res.data.map(f => f.path)
}

async function startCourse(p: StartCoursePayload): Promise<CourseStatusResponse> {
  const res = await api.post<CourseStatusResponse>('/courses', p)
  return res.data
}

async function fetchStatus(threadId: string): Promise<CourseStatusResponse> {
  const res = await api.get<CourseStatusResponse>(`/courses/${threadId}`)
  return res.data
}

async function resumeValidation(threadId: string, approved: boolean): Promise<CourseStatusResponse> {
  const res = await api.post<CourseStatusResponse>(`/courses/${threadId}/validation/resume`, { approved })
  return res.data
}

async function resumeCurriculum(threadId: string, approved: boolean, retry_context: string): Promise<CourseStatusResponse> {
  const res = await api.post<CourseStatusResponse>(`/courses/${threadId}/curriculum/resume`, { approved, retry_context })
  return res.data
}

/* ─── Option constants ─── */
const FORMAT_OPTIONS = [
  { id: 'lesson',        label: 'Lesson',        desc: 'Structured written lesson per session', icon: I.book },
  { id: 'video_script',  label: 'Video Script',  desc: 'Full narration script ready to record', icon: I.eye },
  { id: 'quiz',          label: 'Quiz',           desc: 'Multiple-choice comprehension check', icon: I.check },
  { id: 'worksheet',     label: 'Worksheet',      desc: 'Printable practice exercises', icon: I.layers },
]

const AGE_OPTIONS   = ['Under 10', '10–13', '14–17', '18–24', 'Adult (25+)']
const LEVEL_OPTIONS = ['Beginner', 'Intermediate', 'Advanced']
const TONE_OPTIONS  = ['Formal', 'Casual', 'Encouraging', 'Socratic']

/* ─── Shared sub-components ─── */
function Sec({ title, note, icon }: { title: string; note?: string; icon?: string }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        {icon && (
          <div style={{ width: 26, height: 26, borderRadius: 6, background: '#F7F6F3', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Ico d={icon} size={14} color="var(--ink)" />
          </div>
        )}
        <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)', margin: 0, letterSpacing: '-0.01em' }}>{title}</h3>
      </div>
      {note && <p style={{ fontSize: 13, color: 'var(--ink-muted)', margin: 0, lineHeight: 1.4 }}>{note}</p>}
    </div>
  )
}

function Pill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        fontSize: 13, fontWeight: active ? 600 : 500,
        color: active ? '#fff' : 'var(--ink-muted)',
        background: active ? 'var(--ink)' : '#fff',
        border: `1px solid ${active ? 'var(--ink)' : 'var(--border)'}`,
        padding: '8px 16px', borderRadius: 20, cursor: 'pointer',
        transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
        fontFamily: 'var(--font-sans)',
        boxShadow: active ? '0 4px 12px rgba(0,0,0,0.15)' : '0 1px 2px rgba(0,0,0,0.02)',
      }}
      onMouseEnter={e => { if (!active) e.currentTarget.style.borderColor = '#ccc' }}
      onMouseLeave={e => { if (!active) e.currentTarget.style.borderColor = 'var(--border)' }}
    >
      {label}
    </button>
  )
}

function Stepper({ value, min, max, onChange }: { value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', background: '#FAFAF8' }}>
      <button type="button" onClick={() => onChange(Math.max(min, value - 1))} style={{ width: 36, height: 38, border: 'none', borderRight: '1px solid var(--border)', background: '#fff', fontSize: 18, color: 'var(--ink-muted)', cursor: 'pointer', transition: 'background 150ms' }} onMouseEnter={e => e.currentTarget.style.background = '#F9F9F9'} onMouseLeave={e => e.currentTarget.style.background = '#fff'}>−</button>
      <span style={{ minWidth: 44, textAlign: 'center', fontSize: 16, fontWeight: 700, color: 'var(--ink)', fontFamily: 'var(--font-sans)' }}>{value}</span>
      <button type="button" onClick={() => onChange(Math.min(max, value + 1))} style={{ width: 36, height: 38, border: 'none', borderLeft: '1px solid var(--border)', background: '#fff', fontSize: 18, color: 'var(--ink-muted)', cursor: 'pointer', transition: 'background 150ms' }} onMouseEnter={e => e.currentTarget.style.background = '#F9F9F9'} onMouseLeave={e => e.currentTarget.style.background = '#fff'}>+</button>
    </div>
  )
}

/* ─── Step 4 sub-views ─── */

/** Animated pipeline stage tracker shown while queued / processing */
const PIPELINE_STAGES = [
  { key: 'submitted',   label: 'Course submitted',           sub: 'Your brief is in the queue' },
  { key: 'validating',  label: 'Validating feasibility',     sub: 'Checking scope, cost, and content gaps' },
  { key: 'enriching',   label: 'Enriching knowledge base',   sub: 'Pulling supporting material from the web' },
  { key: 'generating',  label: 'Generating curriculum',      sub: 'Building session-by-session plan' },
  { key: 'reviewing',   label: 'Reviewing output',           sub: 'Critic agent checking coherence' },
]

function stageFromStatus(status: string): number {
  if (status === 'queued')   return 0
  if (status === 'processing') return 1 // advances visually; true stage is unknown
  return -1
}

function ProcessingView({ status }: { status: string }) {
  const activeIdx = stageFromStatus(status)
  return (
    <div style={{ animation: 'enter 300ms ease' }}>
      <div style={{ textAlign: 'center', marginBottom: 32, padding: '8px 0 4px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 52, height: 52, borderRadius: 14, background: '#F7F6F3', marginBottom: 14 }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round" style={{ animation: 'spin 1.8s linear infinite', transformOrigin: 'center' }} />
          </svg>
        </div>
        <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink)', margin: 0 }}>
          {status === 'queued' ? 'Waiting to start…' : 'AI is working on your course'}
        </p>
        <p style={{ fontSize: 13, color: 'var(--ink-muted)', margin: '4px 0 0' }}>This usually takes 2–5 minutes. You can leave and come back.</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {PIPELINE_STAGES.map((s, i) => {
          const done    = i < activeIdx
          const current = i === activeIdx
          const pending = i > activeIdx
          return (
            <div key={s.key} style={{ display: 'flex', gap: 14, paddingBottom: i < PIPELINE_STAGES.length - 1 ? 0 : 0 }}>
              {/* Track */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 24, flexShrink: 0 }}>
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                  border: `2px solid ${done ? 'var(--ink)' : current ? 'var(--ink)' : 'var(--border)'}`,
                  background: done ? 'var(--ink)' : current ? '#fff' : '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 400ms',
                }}>
                  {done && <Ico d={I.check} size={11} color="#fff" />}
                  {current && <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--ink)', display: 'block', animation: 'pulse 1.2s ease infinite' }} />}
                </div>
                {i < PIPELINE_STAGES.length - 1 && (
                  <div style={{ width: 2, flex: 1, minHeight: 24, background: done ? 'var(--ink)' : 'var(--border)', transition: 'background 400ms', margin: '2px 0' }} />
                )}
              </div>
              {/* Content */}
              <div style={{ paddingBottom: 20 }}>
                <p style={{ fontSize: 14, fontWeight: current ? 600 : 500, color: pending ? 'var(--ink-faint)' : 'var(--ink)', margin: '1px 0 2px' }}>{s.label}</p>
                {(done || current) && <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: 0 }}>{s.sub}</p>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** HITL #1 — Validation feasibility report */
function ValidationView({ data, threadId, onResume }: {
  data: Record<string, unknown>
  threadId: string
  onResume: (status: string, d: Record<string, unknown>) => void
}) {
  const flags       = (data.flags as string[])       ?? []
  const suggestions = (data.suggestions as string[]) ?? []
  const cost        = (data.estimated_cost_usd as number) ?? 0
  const report      = (data.feasibility_report as Record<string, unknown>) ?? {}

  const approveM = useMutation({
    mutationFn: () => resumeValidation(threadId, true),
    onSuccess: r => onResume(r.status, r.data),
  })
  const rejectM = useMutation({
    mutationFn: () => resumeValidation(threadId, false),
    onSuccess: r => onResume(r.status, r.data),
  })

  const busy = approveM.isPending || rejectM.isPending

  return (
    <div style={{ animation: 'enter 300ms ease' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-yellow-text)' }} />
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: 0 }}>Pre-flight report</p>
        </div>
        <h3 className="serif" style={{ fontSize: 26, color: 'var(--ink)', margin: 0, letterSpacing: '-0.02em' }}>Validation complete</h3>
        <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '5px 0 0' }}>Review the AI's feasibility assessment before generating your course.</p>
      </div>

      {/* Cost estimate */}
      <div style={{ padding: '14px 18px', background: '#F7F6F3', borderRadius: 10, marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>Estimated generation cost</span>
        <span style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink)', fontFamily: 'var(--font-mono)' }}>${cost.toFixed(2)}</span>
      </div>

      {/* Flags */}
      {flags.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: '0 0 8px' }}>Flags</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {flags.map((f, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px', background: 'var(--accent-yellow-bg)', borderRadius: 8 }}>
                <span style={{ fontSize: 14, flexShrink: 0, marginTop: 1 }}>⚠</span>
                <span style={{ fontSize: 13, color: 'var(--accent-yellow-text)', lineHeight: 1.4 }}>{f}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: '0 0 8px' }}>Suggestions</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {suggestions.map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px', background: '#F7F6F3', borderRadius: 8 }}>
                <span style={{ fontSize: 14, flexShrink: 0, marginTop: 1, color: 'var(--ink-muted)' }}>·</span>
                <span style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.4 }}>{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Raw feasibility keys that aren't flags/suggestions */}
      {Object.keys(report).length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: '0 0 8px' }}>Details</p>
          <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
            {Object.entries(report).map(([k, v], i, arr) => (
              <div key={k} style={{ display: 'flex', gap: 12, padding: '10px 14px', borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink-muted)', minWidth: 120, textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}</span>
                <span style={{ fontSize: 13, color: 'var(--ink)' }}>{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {(approveM.isError || rejectM.isError) && (
        <div style={{ padding: '11px 14px', borderRadius: 8, background: 'var(--accent-red-bg)', color: 'var(--accent-red-text)', fontSize: 13, marginBottom: 16 }}>
          Something went wrong. Please try again.
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
        <button
          type="button"
          onClick={() => rejectM.mutate()}
          disabled={busy}
          style={{ flex: 1, padding: '12px', border: '1px solid var(--border)', borderRadius: 10, background: '#fff', color: 'var(--ink)', fontSize: 14, fontWeight: 600, cursor: busy ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)', opacity: busy ? 0.6 : 1 }}
        >
          Reject — revise brief
        </button>
        <button
          type="button"
          onClick={() => approveM.mutate()}
          disabled={busy}
          style={{ flex: 2, padding: '12px', border: 'none', borderRadius: 10, background: busy ? '#ccc' : 'var(--ink)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: busy ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
        >
          {approveM.isPending ? 'Starting generation…' : <>Approve & continue <Ico d={I.arrow} size={14} color="#fff" /></>}
        </button>
      </div>
    </div>
  )
}

/** HITL #2 — Curriculum review */
interface SessionRow { week: number; session: number; topic: string; objectives: string[] }

function CurriculumView({ data, threadId, onResume }: {
  data: Record<string, unknown>
  threadId: string
  onResume: (status: string, d: Record<string, unknown>) => void
}) {
  const [retryContext, setRetryContext] = useState('')
  const [showRetry, setShowRetry]       = useState(false)

  const plan       = (data.curriculum_plan as Record<string, unknown>) ?? {}
  const retryCount = (data.retry_count as number) ?? 0
  const sessions: SessionRow[] = Array.isArray(plan.sessions) ? (plan.sessions as SessionRow[]) : []

  // Group sessions by week for display
  const byWeek: Record<number, SessionRow[]> = {}
  sessions.forEach(s => {
    if (!byWeek[s.week]) byWeek[s.week] = []
    byWeek[s.week].push(s)
  })

  const approveM = useMutation({
    mutationFn: () => resumeCurriculum(threadId, true, ''),
    onSuccess: r => onResume(r.status, r.data),
  })
  const retryM = useMutation({
    mutationFn: () => resumeCurriculum(threadId, false, retryContext.trim()),
    onSuccess: r => onResume(r.status, r.data),
  })

  const busy = approveM.isPending || retryM.isPending
  const canRetry = retryContext.trim().length > 0

  return (
    <div style={{ animation: 'enter 300ms ease' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-yellow-text)' }} />
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: 0 }}>Curriculum ready</p>
          {retryCount > 0 && (
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-faint)', marginLeft: 'auto' }}>Revision {retryCount}/5</span>
          )}
        </div>
        <h3 className="serif" style={{ fontSize: 26, color: 'var(--ink)', margin: 0, letterSpacing: '-0.02em' }}>Review the curriculum plan</h3>
        <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '5px 0 0' }}>Approve to generate full session content, or request a revision.</p>
      </div>

      {/* Curriculum plan */}
      {sessions.length > 0 ? (
        <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden', marginBottom: 20, maxHeight: 420, overflowY: 'auto' }}>
          {Object.entries(byWeek).map(([week, rows]) => (
            <div key={week}>
              <div style={{ padding: '10px 16px', background: '#F7F6F3', borderBottom: '1px solid var(--border)', position: 'sticky', top: 0 }}>
                <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: 0 }}>Week {week}</p>
              </div>
              {rows.map((s, i) => (
                <div key={i} style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-faint)', minWidth: 64 }}>Session {s.session}</span>
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>{s.topic}</span>
                  </div>
                  {Array.isArray(s.objectives) && s.objectives.length > 0 && (
                    <div style={{ paddingLeft: 72, display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {(s.objectives as string[]).map((o, j) => (
                        <p key={j} style={{ fontSize: 12, color: 'var(--ink-muted)', margin: 0, lineHeight: 1.4 }}>· {o}</p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        /* Fallback: render raw plan as JSON if sessions aren't structured */
        <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px', marginBottom: 20, maxHeight: 320, overflowY: 'auto' }}>
          <pre style={{ fontSize: 12, color: 'var(--ink)', margin: 0, fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {JSON.stringify(plan, null, 2)}
          </pre>
        </div>
      )}

      {/* Retry toggle */}
      {!showRetry ? (
        <button
          type="button"
          onClick={() => setShowRetry(true)}
          style={{ width: '100%', padding: '10px', border: '1px dashed var(--border)', borderRadius: 10, background: 'transparent', color: 'var(--ink-muted)', fontSize: 13, fontWeight: 500, cursor: 'pointer', fontFamily: 'var(--font-sans)', marginBottom: 12 }}
        >
          + Request a revision
        </button>
      ) : (
        <div style={{ marginBottom: 16, animation: 'enter 200ms ease' }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', margin: '0 0 8px' }}>
            What should change? <span style={{ fontWeight: 400, color: 'var(--ink-muted)' }}>(this becomes a hard constraint for the AI)</span>
          </p>
          <textarea
            value={retryContext}
            onChange={e => setRetryContext(e.target.value)}
            placeholder="e.g. Make it shorter, reduce Week 3 sessions, add more practical exercises…"
            style={{
              width: '100%', height: 90, fontSize: 14, color: 'var(--ink)',
              background: '#FAFAF8', border: '1px solid var(--border)',
              borderRadius: 10, padding: '12px 14px', outline: 'none',
              fontFamily: 'var(--font-sans)', boxSizing: 'border-box',
              resize: 'vertical', lineHeight: 1.4,
            }}
            onFocus={e => e.currentTarget.style.borderColor = 'var(--ink)'}
            onBlur={e => e.currentTarget.style.borderColor = 'var(--border)'}
            autoFocus
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
            <button type="button" onClick={() => { setShowRetry(false); setRetryContext('') }} style={{ fontSize: 12, color: 'var(--ink-muted)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
              Cancel
            </button>
            <p style={{ fontSize: 11, color: 'var(--ink-faint)', margin: 0 }}>{retryCount}/5 revisions used</p>
          </div>
        </div>
      )}

      {(approveM.isError || retryM.isError) && (
        <div style={{ padding: '11px 14px', borderRadius: 8, background: 'var(--accent-red-bg)', color: 'var(--accent-red-text)', fontSize: 13, marginBottom: 16 }}>
          Something went wrong. Please try again.
        </div>
      )}

      <div style={{ display: 'flex', gap: 10 }}>
        {showRetry && (
          <button
            type="button"
            onClick={() => retryM.mutate()}
            disabled={busy || !canRetry}
            style={{ flex: 1, padding: '12px', border: '1px solid var(--border)', borderRadius: 10, background: '#fff', color: canRetry ? 'var(--ink)' : 'var(--ink-faint)', fontSize: 14, fontWeight: 600, cursor: (busy || !canRetry) ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)', opacity: (busy || !canRetry) ? 0.6 : 1 }}
          >
            {retryM.isPending ? 'Retrying…' : 'Retry with context'}
          </button>
        )}
        <button
          type="button"
          onClick={() => approveM.mutate()}
          disabled={busy}
          style={{ flex: 2, padding: '12px', border: 'none', borderRadius: 10, background: busy ? '#ccc' : 'var(--ink)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: busy ? 'not-allowed' : 'pointer', fontFamily: 'var(--font-sans)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
        >
          {approveM.isPending ? 'Generating content…' : <>Approve & generate <Ico d={I.arrow} size={14} color="#fff" /></>}
        </button>
      </div>
    </div>
  )
}

/** Terminal states */
function CompletedView({ threadId }: { threadId: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '24px 0', animation: 'enter 400ms ease' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: 16, background: 'var(--accent-green-bg)', marginBottom: 18 }}>
        <Ico d={I.check} size={24} color="var(--accent-green-text)" />
      </div>
      <h3 className="serif" style={{ fontSize: 28, color: 'var(--ink)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Course generated</h3>
      <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '0 0 28px' }}>Your full course pack is ready to view and download.</p>
      <Link to={`/courses/${threadId}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 600, color: '#fff', background: 'var(--ink)', padding: '12px 28px', borderRadius: 10, textDecoration: 'none' }}>
        View course <Ico d={I.arrow} size={14} color="#fff" />
      </Link>
    </div>
  )
}

function RejectedView({ onCancel }: { onCancel: () => void }) {
  return (
    <div style={{ textAlign: 'center', padding: '24px 0', animation: 'enter 400ms ease' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: 16, background: 'var(--accent-red-bg)', marginBottom: 18 }}>
        <Ico d={I.bell} size={24} color="var(--accent-red-text)" />
      </div>
      <h3 className="serif" style={{ fontSize: 26, color: 'var(--ink)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Brief rejected</h3>
      <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '0 0 28px', lineHeight: 1.5 }}>The validation check flagged this brief as not feasible. Start a new course with a revised brief.</p>
      <button type="button" onClick={onCancel} style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', background: '#fff', border: '1px solid var(--border)', padding: '11px 28px', borderRadius: 10, cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
        Start over
      </button>
    </div>
  )
}

function FailedView({ onCancel }: { onCancel: () => void }) {
  return (
    <div style={{ textAlign: 'center', padding: '24px 0', animation: 'enter 400ms ease' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: 16, background: 'var(--accent-red-bg)', marginBottom: 18 }}>
        <Ico d={I.bell} size={24} color="var(--accent-red-text)" />
      </div>
      <h3 className="serif" style={{ fontSize: 26, color: 'var(--ink)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Something went wrong</h3>
      <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '0 0 28px' }}>The pipeline encountered an error. Try submitting again.</p>
      <button type="button" onClick={onCancel} style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', background: '#fff', border: '1px solid var(--border)', padding: '11px 28px', borderRadius: 10, cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
        Try again
      </button>
    </div>
  )
}

/* ══════════════════════════════════════
   Step 4 container — owns polling
══════════════════════════════════════ */
function PipelineView({ threadId, onCancel }: { threadId: string; onCancel: () => void }) {
  // Track what the backend last told us (allow mutations to override without waiting for refetch)
  const [overrideStatus, setOverrideStatus] = useState<string | null>(null)
  const [overrideData,   setOverrideData]   = useState<Record<string, unknown> | null>(null)

  const { data } = useQuery({
    queryKey: ['course-status', threadId],
    queryFn: () => fetchStatus(threadId),
    refetchInterval: q => {
      const s = overrideStatus ?? q.state.data?.status ?? ''
      return (s === 'queued' || s === 'processing') ? 4000 : false
    },
  })

  function handleResume(status: string, d: Record<string, unknown>) {
    setOverrideStatus(status)
    setOverrideData(d)
  }

  const status = overrideStatus ?? data?.status ?? 'queued'
  const payload = overrideData  ?? data?.data   ?? {}

  return (
    <div>
      {(status === 'queued' || status === 'processing') && (
        <ProcessingView status={status} />
      )}
      {status === 'awaiting_validation' && (
        <ValidationView data={payload} threadId={threadId} onResume={handleResume} />
      )}
      {status === 'awaiting_curriculum_review' && (
        <CurriculumView data={payload} threadId={threadId} onResume={handleResume} />
      )}
      {status === 'completed'  && <CompletedView threadId={threadId} />}
      {status === 'rejected'   && <RejectedView  onCancel={onCancel} />}
      {status === 'failed'     && <FailedView     onCancel={onCancel} />}
    </div>
  )
}

/* ══════════════════════════════════════
   ROOT EXPORT — 3-step form + step 4
══════════════════════════════════════ */
export default function NewCourseForm({ onCancel, onSuccess }: { onCancel: () => void; onSuccess: (id: string) => void }) {
  const [step, setStep] = useState(1)
  const [threadId, setThreadId] = useState<string | null>(null)

  // Form state
  const [subject, setSubject]                 = useState('')
  const [formats, setFormats]                 = useState<string[]>(['lesson', 'quiz'])
  const [audienceAge, setAudienceAge]         = useState('')
  const [audienceLevel, setAudienceLevel]     = useState('')
  const [tone, setTone]                       = useState('')
  const [durationWeeks, setDurationWeeks]     = useState(6)
  const [sessionsPerWeek, setSessionsPerWeek] = useState(3)
  const [files, setFiles]                     = useState<File[]>([])
  const [dragOver, setDragOver]               = useState(false)
  const [urlInput, setUrlInput]               = useState('')
  const [enrichmentUrls, setEnrichmentUrls]   = useState<string[]>([])
  const [additionalContext, setAdditionalContext] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const sessionsTotal = durationWeeks * sessionsPerWeek

  const isStep1Valid = Boolean(subject.trim()) && formats.length > 0
  const isStep2Valid = Boolean(audienceAge) && Boolean(audienceLevel) && Boolean(tone)

  const mutation = useMutation({
    mutationFn: async () => {
      const paths = files.length ? await uploadFiles(files) : []
      return startCourse({
        user_id: USER_ID,
        subject: subject.trim(),
        audience_age: audienceAge,
        audience_level: audienceLevel,
        duration_weeks: durationWeeks,
        sessions_per_week: sessionsPerWeek,
        sessions_total: sessionsTotal,
        preferred_formats: formats,
        tone,
        include_quiz: formats.includes('quiz'),
        uploaded_file_paths: paths,
        enrichment_urls: enrichmentUrls,
        additional_context: additionalContext.trim(),
      })
    },
    onSuccess: r => {
      setThreadId(r.thread_id)
      setStep(4)
      onSuccess(r.thread_id)
    },
  })

  function addFiles(incoming: FileList | null) {
    if (!incoming) return
    const valid = Array.from(incoming).filter(f => /\.(pdf|txt|md)$/i.test(f.name))
    setFiles(p => [...p, ...valid])
  }

  function handleAddUrl() {
    const v = urlInput.trim()
    if (v && !enrichmentUrls.includes(v)) setEnrichmentUrls(p => [...p, v])
    setUrlInput('')
  }

  function handleBack() {
    if (step === 2) setStep(1)
    else if (step === 3) setStep(2)
    else onCancel()
  }

  // Step indicator bars: 3 bars for the form steps; step 4 replaces the form
  const progressBars = step === 4
    ? [true, true, true]
    : [step >= 1, step >= 2, step >= 3]

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', animation: 'enter 400ms cubic-bezier(0.16, 1, 0.3, 1) both' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 className="serif" style={{ fontSize: 32, color: 'var(--ink)', margin: 0, lineHeight: 1.1, letterSpacing: '-0.02em' }}>
            {step === 4 ? 'Generating' : 'New Course'}
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ink-muted)', margin: '4px 0 0' }}>
            {step === 4 ? 'Your course is being built — review checkpoints below.' : 'Configure settings and let AI design your curriculum.'}
          </p>
        </div>

        {/* Step progress dots */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {progressBars.map((filled, i) => (
            <div key={i} style={{ width: 32, height: 4, borderRadius: 2, background: filled ? 'var(--ink)' : 'var(--border)', transition: 'background 0.3s' }} />
          ))}
        </div>
      </div>

      <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 16, padding: '32px', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>

        {/* ── STEP 1: BASICS ── */}
        {step === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 32, animation: 'enter 300ms ease' }}>
            <div>
              <Sec title="Course Subject" note="What topic are you creating content for?" icon={I.search} />
              <input
                type="text"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                placeholder="e.g. Graphic Design Basics, GCSE Biology..."
                style={{ width: '100%', fontSize: 16, color: 'var(--ink)', background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px', outline: 'none', fontFamily: 'var(--font-sans)', boxSizing: 'border-box', transition: 'all 200ms', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.02)' }}
                onFocus={e => { e.currentTarget.style.borderColor = 'var(--ink)'; e.currentTarget.style.background = '#fff' }}
                onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = '#FAFAF8' }}
                onKeyDown={e => { if (e.key === 'Enter' && isStep1Valid) { e.preventDefault(); setStep(2) } }}
              />
            </div>

            <div>
              <Sec title="Content Formats" note="Select the materials you need for each session." icon={I.grid} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {FORMAT_OPTIONS.map(f => {
                  const on = formats.includes(f.id)
                  return (
                    <button key={f.id} type="button"
                      onClick={() => setFormats(p => p.includes(f.id) ? p.filter(x => x !== f.id) : [...p, f.id])}
                      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderRadius: 12, cursor: 'pointer', background: on ? '#FAFAF8' : '#fff', border: `1px solid ${on ? 'var(--ink)' : 'var(--border)'}`, textAlign: 'left', fontFamily: 'var(--font-sans)', transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)', boxShadow: on ? '0 2px 8px rgba(0,0,0,0.04)' : 'none' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 32, height: 32, borderRadius: 8, background: on ? 'var(--ink)' : '#F5F5F5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Ico d={f.icon} size={16} color={on ? '#fff' : 'var(--ink-muted)'} />
                        </div>
                        <div>
                          <p style={{ fontSize: 14, fontWeight: on ? 700 : 500, color: 'var(--ink)', margin: 0 }}>{f.label}</p>
                          <p style={{ fontSize: 12, color: 'var(--ink-faint)', margin: '2px 0 0' }}>{f.desc}</p>
                        </div>
                      </div>
                      <div style={{ width: 18, height: 18, borderRadius: 9, border: `2px solid ${on ? 'var(--ink)' : 'var(--border)'}`, background: on ? 'var(--ink)' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {on && <Ico d={I.check} size={12} color="#fff" />}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {/* ── STEP 2: STRATEGY ── */}
        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 32, animation: 'enter 300ms ease' }}>
            <div>
              <Sec title="Target Audience" note="Help AI tailor the reading level and terminology." icon={I.eye} />
              <div style={{ marginBottom: 20 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', margin: '0 0 10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Age Group</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {AGE_OPTIONS.map(a => <Pill key={a} label={a} active={audienceAge === a} onClick={() => setAudienceAge(a)} />)}
                </div>
              </div>
              <div>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', margin: '0 0 10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Experience Level</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {LEVEL_OPTIONS.map(l => <Pill key={l} label={l} active={audienceLevel === l} onClick={() => setAudienceLevel(l)} />)}
                </div>
              </div>
            </div>

            <div>
              <Sec title="Course Tone" note="How should the AI address the learners?" icon={I.settings} />
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {TONE_OPTIONS.map(t => <Pill key={t} label={t} active={tone === t} onClick={() => setTone(t)} />)}
              </div>
            </div>

            <div>
              <Sec title="Curriculum Schedule" note="Set processing scope for generation." icon={I.calendar} />
              <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Duration</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Stepper value={durationWeeks} min={1} max={52} onChange={setDurationWeeks} />
                    <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>weeks</span>
                  </div>
                </div>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pacing</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Stepper value={sessionsPerWeek} min={1} max={7} onChange={setSessionsPerWeek} />
                    <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>sessions/wk</span>
                  </div>
                </div>
              </div>
              <div style={{ marginTop: 20, padding: '14px 16px', background: '#FAFAF8', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ background: 'var(--ink)', width: 24, height: 24, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Ico d={I.layers} size={12} color="#fff" />
                </div>
                <span style={{ fontSize: 14, color: 'var(--ink)' }}>
                  <strong>{sessionsTotal}</strong> total sessions
                </span>
              </div>
            </div>
          </div>
        )}

        {/* ── STEP 3: MATERIALS ── */}
        {step === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 32, animation: 'enter 300ms ease' }}>
            <div>
              <Sec title="Knowledge Base" note="Upload raw notes, text, or syllabi (Optional)." icon={I.upload} />
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files) }}
                onClick={() => fileRef.current?.click()}
                style={{ border: `2px dashed ${dragOver ? 'var(--ink)' : 'var(--border)'}`, borderRadius: 12, padding: '32px 20px', textAlign: 'center', cursor: 'pointer', background: dragOver ? '#F9F9F9' : '#FAFAF8', transition: 'all 200ms ease' }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 48, height: 48, borderRadius: 12, background: '#fff', boxShadow: '0 2px 8px rgba(0,0,0,0.04)', marginBottom: 16 }}>
                  <Ico d={I.upload} size={20} color="var(--ink)" />
                </div>
                <h4 style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink)', margin: '0 0 4px' }}>{dragOver ? 'Drop here' : 'Select files to upload'}</h4>
                <p style={{ fontSize: 13, color: 'var(--ink-faint)', margin: 0 }}>PDF · TXT · Markdown</p>
              </div>
              <input ref={fileRef} type="file" multiple accept=".pdf,.txt,.md" style={{ display: 'none' }} onChange={e => addFiles(e.target.files)} />

              {files.length > 0 && (
                <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {files.map((f, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Ico d={I.book} size={14} color="var(--ink-muted)" />
                        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)' }}>{f.name}</span>
                        <span style={{ fontSize: 11, color: 'var(--ink-faint)' }}>({(f.size / 1024).toFixed(0)} KB)</span>
                      </div>
                      <button type="button" onClick={() => setFiles(p => p.filter((_, j) => j !== i))} style={{ fontSize: 12, color: 'var(--ink-muted)', background: 'none', border: 'none', cursor: 'pointer' }}>Remove</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <Sec title="Enrichment URLs" note="Link to articles or videos (Optional)." icon={I.layers} />
              <div style={{ display: 'flex', gap: 8 }}>
                <input type="text" value={urlInput} onChange={e => setUrlInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddUrl() } }} placeholder="https://..."
                  style={{ flex: 1, fontSize: 14, color: 'var(--ink)', background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 14px', outline: 'none', fontFamily: 'var(--font-mono)', boxSizing: 'border-box' }} />
                <button type="button" onClick={handleAddUrl} style={{ padding: '0 20px', borderRadius: 10, border: '1px solid var(--border)', background: '#fff', color: 'var(--ink)', fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>Add</button>
              </div>
              {enrichmentUrls.length > 0 && (
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {enrichmentUrls.map((url, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden' }}>
                        <Ico d={I.layers} size={14} color="var(--ink-muted)" />
                        <span style={{ fontSize: 13, color: 'var(--ink)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{url}</span>
                      </div>
                      <button type="button" onClick={() => setEnrichmentUrls(p => p.filter((_, j) => j !== i))} style={{ fontSize: 12, color: 'var(--ink-muted)', background: 'none', border: 'none', cursor: 'pointer', paddingLeft: 12 }}>Remove</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <Sec title="Additional Context" note="Any specific requirements for the AI? (Optional)" icon={I.check} />
              <textarea value={additionalContext} onChange={e => setAdditionalContext(e.target.value)} placeholder="e.g. Focus heavily on practical examples, avoid extensive theory…"
                style={{ width: '100%', height: 100, fontSize: 14, color: 'var(--ink)', background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 14px', outline: 'none', fontFamily: 'var(--font-sans)', boxSizing: 'border-box', resize: 'vertical', lineHeight: 1.4 }} />
            </div>

            {mutation.isError && (
              <div style={{ padding: '12px 16px', borderRadius: 10, background: 'var(--accent-red-bg)', color: 'var(--accent-red-text)', fontSize: 14, fontWeight: 500 }}>
                {(mutation.error as Error)?.message ?? 'An error occurred.'}
              </div>
            )}
          </div>
        )}

        {/* ── STEP 4: PIPELINE ── */}
        {step === 4 && threadId && (
          <PipelineView threadId={threadId} onCancel={onCancel} />
        )}

        {/* ── Footer (steps 1–3 only) ── */}
        {step < 4 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 40, paddingTop: 24, borderTop: '1px solid var(--border)' }}>
            <button type="button" onClick={handleBack} style={{ padding: '10px 20px', color: 'var(--ink)', background: 'transparent', border: '1px solid var(--border)', borderRadius: 10, cursor: 'pointer', fontWeight: 600, fontSize: 14, fontFamily: 'var(--font-sans)' }}>
              {step === 1 ? 'Cancel' : 'Back'}
            </button>

            {step < 3 ? (
              <button type="button" onClick={() => setStep(s => s + 1)} disabled={step === 1 ? !isStep1Valid : !isStep2Valid}
                style={{ padding: '10px 24px', color: '#fff', background: (step === 1 ? isStep1Valid : isStep2Valid) ? 'var(--ink)' : '#d1d1d1', border: 'none', borderRadius: 10, cursor: (step === 1 ? isStep1Valid : isStep2Valid) ? 'pointer' : 'not-allowed', fontWeight: 600, fontSize: 14, fontFamily: 'var(--font-sans)', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
                Continue
              </button>
            ) : (
              <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending}
                style={{ padding: '10px 24px', color: '#fff', background: !mutation.isPending ? 'var(--ink)' : '#d1d1d1', border: 'none', borderRadius: 10, cursor: !mutation.isPending ? 'pointer' : 'not-allowed', fontWeight: 600, fontSize: 14, fontFamily: 'var(--font-sans)', boxShadow: '0 4px 12px rgba(0,0,0,0.15)', display: 'flex', alignItems: 'center', gap: 8 }}>
                {mutation.isPending ? 'Starting…' : <><span>Generate Course</span><Ico d={I.arrow} size={14} color="#fff" /></>}
              </button>
            )}
          </div>
        )}
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
