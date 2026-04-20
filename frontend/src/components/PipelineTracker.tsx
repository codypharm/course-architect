import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Ico, I } from './Icon'
import { Markdown } from './Markdown'

export interface CourseStatusResponse {
  thread_id: string
  status: string
  data: Record<string, unknown>
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

/** Animated pipeline stage tracker shown while queued / processing */
const PIPELINE_STAGES = [
  { key: 'submitted',   label: 'Course submitted',           sub: 'Your brief is in the queue' },
  { key: 'validating',  label: 'Validating feasibility',     sub: 'Checking scope, cost, and content gaps' },
  { key: 'enriching',   label: 'Enriching knowledge base',   sub: 'Pulling supporting material from the web' },
  { key: 'generating',  label: 'Generating curriculum',      sub: 'Building session-by-session plan' },
  { key: 'reviewing',   label: 'Reviewing output',           sub: 'Critic agent checking coherence' },
]

function stageFromStatus(status: string, minStage = 0, serverStage?: number): number {
  if (status === 'queued')     return 0
  if (status === 'processing') return Math.max(1, minStage, serverStage ?? 0)
  return -1
}

function ProcessingView({ status, minStage = 0, serverStage }: { status: string; minStage?: number; serverStage?: number }) {
  const activeIdx = stageFromStatus(status, minStage, serverStage)
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
  onResume: (status: string, d: Record<string, unknown>, minStage?: number) => void
}) {
  const flags       = (data.flags as string[])       ?? []
  const suggestions = (data.suggestions as string[]) ?? []
  const cost        = (data.estimated_cost_usd as number) ?? 0
  const report      = (data.feasibility_report as Record<string, unknown>) ?? {}

  const approveM = useMutation({
    mutationFn: () => resumeValidation(threadId, true),
    onSuccess: r => onResume(r.status, r.data, 2), // post-validation: enriching stage
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

      {/* Feasibility report details — each value is {ok: bool, note: string} */}
      {Object.keys(report).length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: '0 0 8px' }}>Details</p>
          <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
            {Object.entries(report).map(([k, v], i, arr) => {
              const item = v as { ok?: boolean; note?: string }
              const ok   = item?.ok
              const note = item?.note ?? String(v)
              return (
                <div key={k} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '10px 14px', borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink-muted)', minWidth: 140, textTransform: 'capitalize', paddingTop: 1 }}>{k.replace(/_/g, ' ')}</span>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 7, flex: 1 }}>
                    {ok !== undefined && (
                      <span style={{ fontSize: 13, flexShrink: 0, color: ok ? 'var(--accent-green-text)' : 'var(--accent-yellow-text)', fontWeight: 600 }}>
                        {ok ? '✓' : '✗'}
                      </span>
                    )}
                    <span style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.4 }}>{note}</span>
                  </div>
                </div>
              )
            })}
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
interface SessionRow {
  week: number; session: number; topic: string; objectives: string[]
  lesson_outline: string[]; lesson_content: string
  video_script: string; quiz_questions: unknown[]; worksheet_exercises: string[]
}

const FORMAT_BADGE: { key: keyof SessionRow; label: string }[] = [
  { key: 'lesson_content',        label: 'Lesson' },
  { key: 'video_script',          label: 'Script' },
  { key: 'quiz_questions',        label: 'Quiz' },
  { key: 'worksheet_exercises',   label: 'Worksheet' },
]

function hasContent(v: unknown): boolean {
  if (typeof v === 'string')  return v.trim().length > 0
  if (Array.isArray(v))       return v.length > 0
  return false
}

/** Expandable session row with format badges and content preview. */
function SessionRowCard({ s }: { s: SessionRow }) {
  const [open, setOpen] = useState(false)
  const badges = FORMAT_BADGE.filter(b => hasContent(s[b.key]))

  return (
    <div style={{ borderBottom: '1px solid var(--border)' }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{ width: '100%', textAlign: 'left', padding: '12px 16px', background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: badges.length ? 6 : 0 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-faint)', minWidth: 64, flexShrink: 0 }}>Session {s.session}</span>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', flex: 1 }}>{s.topic}</span>
          <span style={{ fontSize: 11, color: 'var(--ink-faint)', flexShrink: 0 }}>{open ? '▲' : '▼'}</span>
        </div>
        {badges.length > 0 && (
          <div style={{ paddingLeft: 72, display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {badges.map(b => (
              <span key={b.key} style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', padding: '2px 7px', borderRadius: 9999, background: 'var(--accent-green-bg)', color: 'var(--accent-green-text)' }}>
                ✓ {b.label}
              </span>
            ))}
          </div>
        )}
      </button>

      {open && (
        <div style={{ padding: '0 16px 14px', paddingLeft: 88 }}>
          {/* Objectives */}
          {s.objectives?.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-faint)', margin: '0 0 5px' }}>Objectives</p>
              {s.objectives.map((o, i) => <p key={i} style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 2px', lineHeight: 1.4 }}>· {o}</p>)}
            </div>
          )}
          {/* Lesson preview */}
          {s.lesson_content?.trim() && (
            <div style={{ marginBottom: 14 }}>
              <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-faint)', margin: '0 0 5px' }}>Lesson preview</p>
              <div style={{ maxHeight: 90, overflow: 'hidden', WebkitMaskImage: 'linear-gradient(to bottom, black 40%, transparent 100%)', pointerEvents: 'none' }}>
                <Markdown content={s.lesson_content} />
              </div>
            </div>
          )}
          {/* Video script preview */}
          {s.video_script?.trim() && (
            <div style={{ marginBottom: 14 }}>
              <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-faint)', margin: '0 0 5px' }}>Script preview</p>
              <div style={{ maxHeight: 90, overflow: 'hidden', WebkitMaskImage: 'linear-gradient(to bottom, black 40%, transparent 100%)', pointerEvents: 'none' }}>
                <Markdown content={s.video_script} />
              </div>
            </div>
          )}
          {/* Quiz count */}
          {s.quiz_questions?.length > 0 && (
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: 0 }}>
              {s.quiz_questions.length} quiz question{s.quiz_questions.length !== 1 ? 's' : ''} generated
            </p>
          )}
          {/* Worksheet count */}
          {s.worksheet_exercises?.length > 0 && (
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '4px 0 0' }}>
              {s.worksheet_exercises.length} worksheet exercise{s.worksheet_exercises.length !== 1 ? 's' : ''} generated
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function CurriculumView({ data, threadId, onResume }: {
  data: Record<string, unknown>
  threadId: string
  onResume: (status: string, d: Record<string, unknown>, minStage?: number) => void
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
    onSuccess: r => onResume(r.status, r.data, 4), // post-curriculum: reviewing stage
  })
  const retryM = useMutation({
    mutationFn: () => resumeCurriculum(threadId, false, retryContext.trim()),
    onSuccess: r => onResume(r.status, r.data, 3), // retry: back to generating
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
        <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '5px 0 0' }}>Full content has been generated. Review each session below, then approve or request changes.</p>
      </div>

      {/* Curriculum plan */}
      {sessions.length > 0 ? (
        <>
          <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 8px' }}>
            {Object.keys(byWeek).length} week{Object.keys(byWeek).length !== 1 ? 's' : ''} · {sessions.length} session{sessions.length !== 1 ? 's' : ''}
          </p>
          <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden', marginBottom: 20 }}>
            {Object.entries(byWeek).map(([week, rows]) => (
              <div key={week}>
                <div style={{ padding: '10px 16px', background: '#F7F6F3', borderBottom: '1px solid var(--border)', position: 'sticky', top: 0 }}>
                  <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: 0 }}>Week {week}</p>
                </div>
                {rows.map((s, i) => <SessionRowCard key={i} s={s} />)}
              </div>
            ))}
          </div>
        </>
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
            placeholder="e.g. Use simpler language, add more quizzes, make Week 2 deeper… Session count and duration are fixed from your original brief and cannot be changed here."
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

function RejectedView({ onReset, onRevise }: { onReset: () => void; onRevise?: () => void }) {
  return (
    <div style={{ textAlign: 'center', padding: '24px 0', animation: 'enter 400ms ease' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: 16, background: 'var(--accent-red-bg)', marginBottom: 18 }}>
        <Ico d={I.bell} size={24} color="var(--accent-red-text)" />
      </div>
      <h3 className="serif" style={{ fontSize: 26, color: 'var(--ink)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Brief rejected</h3>
      <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '0 0 28px', lineHeight: 1.5 }}>
        The validation check flagged issues with this brief. Revise your settings and try again — your previous answers will be carried over.
      </p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
        {onRevise && (
          <button type="button" onClick={onRevise} style={{ fontSize: 14, fontWeight: 600, color: '#fff', background: 'var(--ink)', border: 'none', padding: '11px 28px', borderRadius: 10, cursor: 'pointer', fontFamily: 'var(--font-sans)', boxShadow: '0 4px 12px rgba(0,0,0,0.12)' }}>
            Revise brief
          </button>
        )}
        <button type="button" onClick={onReset} style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', background: '#fff', border: '1px solid var(--border)', padding: '11px 28px', borderRadius: 10, cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
          Start over
        </button>
      </div>
    </div>
  )
}

function FailedView({ onReset }: { onReset: () => void }) {
  return (
    <div style={{ textAlign: 'center', padding: '24px 0', animation: 'enter 400ms ease' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: 16, background: 'var(--accent-red-bg)', marginBottom: 18 }}>
        <Ico d={I.bell} size={24} color="var(--accent-red-text)" />
      </div>
      <h3 className="serif" style={{ fontSize: 26, color: 'var(--ink)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Something went wrong</h3>
      <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '0 0 28px' }}>The pipeline encountered an error. Try submitting again.</p>
      <button type="button" onClick={onReset} style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', background: '#fff', border: '1px solid var(--border)', padding: '11px 28px', borderRadius: 10, cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
        Try again
      </button>
    </div>
  )
}

/* ══════════════════════════════════════
   Step 4 container — owns polling
══════════════════════════════════════ */
export default function PipelineTracker({ threadId, onReset, onRevise }: { threadId: string; onReset: () => void; onRevise?: () => void }) {
  // Track what the backend last told us (allow mutations to override without waiting for refetch)
  const [overrideStatus,   setOverrideStatus]   = useState<string | null>(null)
  const [overrideData,     setOverrideData]     = useState<Record<string, unknown> | null>(null)
  const [processingMinStage, setProcessingMinStage] = useState(0)

  const { data } = useQuery({
    queryKey: ['course-status', threadId],
    queryFn: () => fetchStatus(threadId),
    refetchInterval: q => {
      const s = overrideStatus ?? q.state.data?.status ?? ''
      return (s === 'queued' || s === 'processing') ? 4000 : false
    },
  })

  // When the query settles to a stable (non-transient) state, drop the
  // optimistic override so the real status drives the UI.
  useEffect(() => {
    const qs = data?.status
    if (qs && qs !== 'queued' && qs !== 'processing') {
      setOverrideStatus(null)
      setOverrideData(null)
    }
  }, [data?.status])

  function handleResume(status: string, d: Record<string, unknown>, minStage = 0) {
    setOverrideStatus(status)
    setOverrideData(d)
    if (minStage > 0) setProcessingMinStage(minStage)
  }

  const status = overrideStatus ?? data?.status ?? 'queued'
  const payload = overrideData  ?? data?.data   ?? {}

  return (
    <div>
      {(status === 'queued' || status === 'processing') && (
        <ProcessingView
          status={status}
          minStage={processingMinStage}
          serverStage={data?.data?.processing_stage as number | undefined}
        />
      )}
      {status === 'awaiting_validation' && (
        <ValidationView data={payload} threadId={threadId} onResume={handleResume} />
      )}
      {status === 'awaiting_curriculum_review' && (
        <CurriculumView data={payload} threadId={threadId} onResume={handleResume} />
      )}
      {status === 'completed'  && <CompletedView threadId={threadId} />}
      {status === 'rejected'   && <RejectedView onReset={onReset} onRevise={onRevise} />}
      {status === 'failed'     && <FailedView onReset={onReset} />}
    </div>
  )
}
