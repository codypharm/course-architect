import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { CourseListItem, CourseStatus } from '@/types/course'
import { Ico, I } from '@/components/Icon'
import NewCourseForm from '@/components/NewCourseForm'

const USER_ID = 'demo-user'

/* ─── API ─── */
async function fetchCourses(): Promise<CourseListItem[]> {
  const res = await api.get<CourseListItem[]>(`/users/${USER_ID}/courses`)
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



/* ─── Status badge ─── */
function Badge({ status }: { status: CourseStatus }) {
  const b = STATUS_BADGE[status]
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', padding: '3px 9px', borderRadius: 9999, background: b.bg, color: b.color, whiteSpace: 'nowrap' }}>
      {b.live && <span style={{ width: 5, height: 5, borderRadius: '50%', background: b.color, display: 'inline-block', animation: 'pulse 1.2s ease infinite' }} />}
      {b.label}
    </span>
  )
}

/* ─── Course thumbnail ─── */
function Thumb({ subject }: { subject: string }) {
  const paths = [I.book, I.layers, I.settings, I.grid]
  const p = paths[subject.length % paths.length]
  return (
    <div style={{ width: 42, height: 42, borderRadius: 8, background: '#F7F6F3', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <Ico d={p} size={19} color="var(--ink-muted)" />
    </div>
  )
}

/* ─── Active project card ─── */
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
function CompletedRow({ course }: { course: CourseListItem }) {
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
        <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 500, color: 'var(--ink)', padding: '5px 10px', border: '1px solid var(--border)', borderRadius: 6, background: '#fff', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
          <Ico d={I.download} size={12} /> Download
        </button>
      </div>
    </div>
  )
}



/* ══════════════════════════════════════
   DASHBOARD PAGE
══════════════════════════════════════ */
type NavItem = 'dashboard' | 'new' | 'settings'

const NAV_ITEMS: { id: NavItem; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: I.grid },
  { id: 'new',       label: 'New Course', icon: I.plus },
  { id: 'settings',  label: 'Settings',   icon: I.settings },
]

export default function DashboardPage() {
  const [nav, setNav]       = useState<NavItem>('dashboard')
  const [search, setSearch] = useState('')
  const qc = useQueryClient()

  const { data: courses, isLoading } = useQuery({
    queryKey: ['courses', USER_ID],
    queryFn: fetchCourses,
    refetchInterval: q => q.state.data?.some(c => isActive(c.status)) ? 5000 : false,
  })

  const active    = (courses ?? []).filter(c => isActive(c.status))
  const completed = (courses ?? []).filter(c => c.status === 'completed')
  const searched  = search.trim()
    ? (courses ?? []).filter(c => c.subject.toLowerCase().includes(search.toLowerCase()))
    : null

  function handleSuccess(threadId: string) {
    qc.invalidateQueries({ queryKey: ['courses', USER_ID] })
    window.location.href = `/courses/${threadId}`
  }

  /* ── Logo mark ── */
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
              <button key={item.id} onClick={() => setNav(item.id)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '9px 12px', borderRadius: 7, marginBottom: 2, background: on ? '#F7F6F3' : 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', color: on ? 'var(--ink)' : 'var(--ink-muted)', fontWeight: on ? 600 : 400, fontSize: 14, textAlign: 'left', transition: 'background 150ms' }}>
                <Ico d={item.icon} size={15} color={on ? 'var(--ink)' : 'var(--ink-muted)'} />
                {item.label}
                {on && <div style={{ marginLeft: 'auto', width: 3, height: 14, borderRadius: 2, background: 'var(--ink)' }} />}
              </button>
            )
          })}
        </nav>

        <div style={{ padding: '12px 14px 20px' }}>
          <button onClick={() => setNav('new')} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, padding: '11px', borderRadius: 8, background: 'var(--ink)', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-sans)' }}>
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
          <button onClick={() => setNav('dashboard')} style={{ fontSize: 12, color: 'var(--ink-muted)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>Cancel</button>
        )}
      </div>

      {/* ── Main content ── */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        {/* Desktop header */}
        <header style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '0 24px', height: 58, background: '#fff', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ flex: 1 }}>
            {nav === 'dashboard' && <>
              <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>Welcome back</h1>
              <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: 0 }}>Here is the status of your course portfolio.</p>
            </>}
            {nav === 'new' && <h1 style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>New Course</h1>}
            {nav === 'settings' && <h1 style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>Settings</h1>}
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
        </header>

        {/* Page body */}
        <main className="dash-content-pad" style={{ flex: 1, padding: '24px', paddingTop: '68px', overflowY: 'auto' }}>

          {/* ── Dashboard ── */}
          {nav === 'dashboard' && (
            <div style={{ paddingTop: 0 }}>
              {/* Search results */}
              {searched && (
                <section style={{ marginBottom: 32 }}>
                  <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', margin: '0 0 4px' }}>Search results</h2>
                  <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 14px' }}>{searched.length} match{searched.length !== 1 ? 'es' : ''} for "{search}"</p>
                  <div className="course-grid">{searched.map(c => isActive(c.status) ? <ActiveCard key={c.thread_id} course={c} /> : <CompletedRow key={c.thread_id} course={c} />)}</div>
                </section>
              )}

              {!searched && <>
                {/* Active projects */}
                <section style={{ marginBottom: 32 }}>
                  <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', margin: '0 0 3px' }}>Active Projects</h2>
                  <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 14px' }}>Courses currently in the generation pipeline.</p>
                  {isLoading ? (
                    <div className="course-grid">{[1, 2].map(i => <div key={i} style={{ height: 170, borderRadius: 10, background: '#EAEAEA', animation: `enter 400ms ease both ${i * 80}ms` }} />)}</div>
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

                {/* Completed */}
                {completed.length > 0 && (
                  <section>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
                      <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>Completed Courses</h2>
                      <span style={{ fontSize: 13, color: 'var(--ink-muted)', cursor: 'pointer', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4 }}>
                        View All <Ico d={I.arrow} size={12} color="var(--ink-muted)" />
                      </span>
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '0 0 14px' }}>Finalised course packs ready to use.</p>
                    <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 10, padding: '0 18px' }}>
                      {completed.map(c => <CompletedRow key={c.thread_id} course={c} />)}
                    </div>
                  </section>
                )}
              </>}
            </div>
          )}

          {/* ── New Course ── */}
          {nav === 'new' && <NewCourseForm onCancel={() => setNav('dashboard')} onSuccess={handleSuccess} />}

          {/* ── Settings ── */}
          {nav === 'settings' && <p style={{ fontSize: 14, color: 'var(--ink-muted)', paddingTop: 12 }}>Settings coming soon.</p>}
        </main>
      </div>

      {/* ── Mobile bottom nav ── */}
      <nav className="dash-bottom-nav">
        {NAV_ITEMS.map(item => {
          const on = nav === item.id
          return (
            <button key={item.id} onClick={() => setNav(item.id)} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3, border: 'none', background: 'transparent', cursor: 'pointer', color: on ? 'var(--ink)' : 'var(--ink-faint)', fontFamily: 'var(--font-sans)' }}>
              <Ico d={item.icon} size={18} color={on ? 'var(--ink)' : 'var(--ink-faint)'} />
              <span style={{ fontSize: 10, fontWeight: on ? 600 : 400 }}>{item.label}</span>
            </button>
          )
        })}
      </nav>
    </div>
  )
}
