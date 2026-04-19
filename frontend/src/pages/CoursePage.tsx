import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Ico, I } from '@/components/Icon'

import { type CourseData, type CurriculumPlan, type SessionPlan } from '@/types/course'
import { CourseSidebar } from '@/components/course/CourseSidebar'
import { CourseOverview } from '@/components/course/CourseOverview'
import { SessionPanel } from '@/components/course/SessionPanel'

async function fetchCourse(threadId: string): Promise<CourseData> {
  const res = await api.get<{ thread_id: string; status: string; data: Record<string, unknown> }>(
    `/courses/${threadId}`,
  )
  return res.data as CourseData
}

export default function CoursePage() {
  const { threadId } = useParams<{ threadId: string }>()
  const [activeSession, setActiveSession] = useState<number>(-1) // Default to overview

  const { data, isLoading, isError } = useQuery({
    queryKey: ['course-detail', threadId],
    queryFn: () => fetchCourse(threadId!),
    enabled: !!threadId,
  })

  const plan: CurriculumPlan | null = (data?.data?.curriculum_plan as CurriculumPlan) ?? null
  const sessions: SessionPlan[] = plan?.sessions ?? (data?.data?.session_content as SessionPlan[]) ?? []

  // Group by week for the sidebar nav
  const byWeek: Record<number, SessionPlan[]> = {}
  sessions.forEach(s => {
    if (!byWeek[s.week]) byWeek[s.week] = []
    byWeek[s.week].push(s)
  })

  const current = sessions[activeSession] ?? null

  return (
    <div style={{ minHeight: '100vh', background: '#F5F6FA', fontFamily: 'var(--font-sans)', display: 'flex', flexDirection: 'column' }}>
      
      {/* Top bar */}
      <header style={{ background: '#fff', borderBottom: '1px solid var(--border)', padding: '0 32px', height: 60, display: 'flex', alignItems: 'center', gap: 14, position: 'sticky', top: 0, zIndex: 20, boxShadow: '0 1px 2px rgba(0,0,0,0.02)' }}>
        <Link to="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--ink-muted)', textDecoration: 'none', fontWeight: 600, transition: 'color 200ms' }} onMouseEnter={e => e.currentTarget.style.color = 'var(--ink)'} onMouseLeave={e => e.currentTarget.style.color = 'var(--ink-muted)'}>
          <Ico d={I.arrow} size={12} style={{ transform: 'rotate(180deg)' }} />
          Dashboard
        </Link>
        <span style={{ color: 'var(--border)', fontSize: 16 }}>/</span>
        {isLoading ? (
          <span style={{ height: 14, width: 160, background: '#EAEAEA', borderRadius: 4, display: 'inline-block' }} />
        ) : (
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>{plan?.course_overview ? 'Curriculum Viewer' : 'Course Viewer'}</span>
        )}
      </header>

      {/* Loading State */}
      {isLoading && (
        <div style={{ maxWidth: 1000, margin: '48px auto', padding: '0 24px', width: '100%', display: 'flex', gap: 32 }}>
          <div style={{ width: 260, flexShrink: 0 }}>
             {[200, 140, 180, 120, 160].map((w, i) => (
                <div key={i} style={{ height: 16, width: `${w}px`, background: '#EAEAEA', borderRadius: 4, marginBottom: 16, animation: `pulse 1.5s infinite ease-in-out ${i * 100}ms` }} />
              ))}
          </div>
          <div style={{ flex: 1 }}>
             <div style={{ height: 40, width: 300, background: '#EAEAEA', borderRadius: 8, marginBottom: 24, animation: `pulse 1.5s infinite ease-in-out` }} />
             <div style={{ height: 18, width: '100%', background: '#EAEAEA', borderRadius: 4, marginBottom: 12, animation: `pulse 1.5s infinite ease-in-out 100ms` }} />
             <div style={{ height: 18, width: '90%', background: '#EAEAEA', borderRadius: 4, marginBottom: 12, animation: `pulse 1.5s infinite ease-in-out 200ms` }} />
             <div style={{ height: 18, width: '60%', background: '#EAEAEA', borderRadius: 4, marginBottom: 12, animation: `pulse 1.5s infinite ease-in-out 300ms` }} />
          </div>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center', background: '#fff', border: '1px solid var(--border)', borderRadius: 16, padding: '40px', boxShadow: '0 4px 12px rgba(0,0,0,0.02)' }}>
            <h3 style={{ fontSize: 20, color: 'var(--ink)', margin: '0 0 8px' }}>Could not load course</h3>
            <p style={{ fontSize: 14, color: 'var(--ink-muted)', margin: '0 0 24px' }}>There was an error fetching this data from the server.</p>
            <Link to="/dashboard" style={{ display: 'inline-flex', padding: '10px 20px', background: 'var(--ink)', color: '#fff', borderRadius: 8, textDecoration: 'none', fontSize: 14, fontWeight: 600 }}>
              Back to dashboard
            </Link>
          </div>
        </div>
      )}

      {/* Main Content */}
      {!isLoading && !isError && data && (
        <div style={{ maxWidth: 1200, width: '100%', margin: '0 auto', padding: '32px 24px', display: 'flex', gap: 32, alignItems: 'flex-start', flex: 1 }}>

          {/* Extracted Sidebar Navigation */}
          <CourseSidebar 
            sessions={sessions} 
            byWeek={byWeek} 
            activeSession={activeSession} 
            onSelect={setActiveSession} 
          />

          {/* Content Area */}
          <main style={{ flex: 1, minWidth: 0 }}>
            {activeSession === -1 && plan && (
              <CourseOverview plan={plan} sessions={sessions} byWeek={byWeek} />
            )}

            {activeSession >= 0 && current && (
              <SessionPanel session={current} />
            )}

            {sessions.length === 0 && activeSession >= 0 && (
              <div style={{ background: '#fff', border: '1px border', borderRadius: 12, padding: '60px 24px', textAlign: 'center' }}>
                <p style={{ fontSize: 15, color: 'var(--ink-muted)', margin: 0 }}>No session content available for this course.</p>
              </div>
            )}
          </main>
          
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0% { opacity: 0.6; }
          50% { opacity: 1; }
          100% { opacity: 0.6; }
        }
      `}</style>
    </div>
  )
}
