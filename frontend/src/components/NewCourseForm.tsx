import { useState, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Ico, I } from './Icon'
import PipelineTracker, { type CourseStatusResponse } from './PipelineTracker'

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

/* ─── Types ─── */
export interface CourseBrief {
  subject?: string
  formats?: string[]
  audienceAge?: string
  audienceLevel?: string
  tone?: string
  durationWeeks?: number
  sessionsPerWeek?: number
  enrichmentUrls?: string[]
  additionalContext?: string
  uploadedFilePaths?: string[]  // S3 keys carried over from a rejected brief
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

/* ══════════════════════════════════════
   ROOT EXPORT — 3-step form + step 4
══════════════════════════════════════ */
export default function NewCourseForm({ onCancel, onSuccess, onReset, initialValues, onRevise }: {
  onCancel: () => void
  onSuccess: (id: string) => void
  onReset: () => void
  initialValues?: CourseBrief
  onRevise?: (threadId: string) => void
}) {
  const [step, setStep] = useState(1)
  const [threadId, setThreadId] = useState<string | null>(null)

  // Form state — seeded from initialValues when revising a rejected brief
  const [subject, setSubject]                 = useState(initialValues?.subject ?? '')
  const [formats, setFormats]                 = useState<string[]>(initialValues?.formats ?? ['lesson', 'quiz'])
  const [audienceAge, setAudienceAge]         = useState(initialValues?.audienceAge ?? '')
  const [audienceLevel, setAudienceLevel]     = useState(initialValues?.audienceLevel ?? '')
  const [tone, setTone]                       = useState(initialValues?.tone ?? '')
  const [durationWeeks, setDurationWeeks]     = useState(initialValues?.durationWeeks ?? 6)
  const [sessionsPerWeek, setSessionsPerWeek] = useState(initialValues?.sessionsPerWeek ?? 3)
  const [files, setFiles]                     = useState<File[]>([])
  // S3 keys from a previously rejected brief — submitted as-is, no re-upload needed
  const [carriedPaths, setCarriedPaths]       = useState<string[]>(initialValues?.uploadedFilePaths ?? [])
  const [dragOver, setDragOver]               = useState(false)
  const [urlInput, setUrlInput]               = useState('')
  const [enrichmentUrls, setEnrichmentUrls]   = useState<string[]>(initialValues?.enrichmentUrls ?? [])
  const [additionalContext, setAdditionalContext] = useState(initialValues?.additionalContext ?? '')
  const fileRef = useRef<HTMLInputElement>(null)

  const sessionsTotal = durationWeeks * sessionsPerWeek

  const isStep1Valid = Boolean(subject.trim()) && formats.length > 0
  const isStep2Valid = Boolean(audienceAge) && Boolean(audienceLevel) && Boolean(tone)

  const mutation = useMutation({
    mutationFn: async () => {
      const newPaths = files.length ? await uploadFiles(files) : []
      const paths = [...carriedPaths, ...newPaths]
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

              {carriedPaths.length > 0 && (
                <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-muted)', margin: '0 0 4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Carried over from previous brief</p>
                  {carriedPaths.map((key, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: '#F7F6F3', border: '1px solid var(--border)', borderRadius: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Ico d={I.book} size={14} color="var(--ink-muted)" />
                        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)' }}>{key.split('/').pop()}</span>
                      </div>
                      <button type="button" onClick={() => setCarriedPaths(p => p.filter((_, j) => j !== i))} style={{ fontSize: 12, color: 'var(--ink-muted)', background: 'none', border: 'none', cursor: 'pointer' }}>Remove</button>
                    </div>
                  ))}
                </div>
              )}

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
          <PipelineTracker threadId={threadId} onReset={onReset} onRevise={onRevise ? () => onRevise(threadId) : undefined} />
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
