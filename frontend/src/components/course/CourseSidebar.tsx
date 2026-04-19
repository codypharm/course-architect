import { type SessionPlan } from '@/types/course'

interface CourseSidebarProps {
  sessions: SessionPlan[]
  byWeek: Record<number, SessionPlan[]>
  activeSession: number
  onSelect: (index: number) => void
}

export function CourseSidebar({ sessions, byWeek, activeSession, onSelect }: CourseSidebarProps) {
  return (
    <aside style={{ width: 260, flexShrink: 0, position: 'sticky', top: 80, maxHeight: 'calc(100vh - 100px)', overflowY: 'auto', background: '#fff', border: '1px solid var(--border)', borderRadius: 16, padding: '16px 0', boxShadow: '0 4px 12px rgba(0,0,0,0.02)' }}>
      {/* Overview item */}
      <button
        onClick={() => onSelect(-1)}
        style={{
          width: '100%', textAlign: 'left', padding: '10px 20px',
          background: activeSession === -1 ? '#FAFAF8' : 'transparent',
          border: 'none', borderLeft: `3px solid ${activeSession === -1 ? 'var(--ink)' : 'transparent'}`,
          cursor: 'pointer', fontFamily: 'var(--font-sans)', marginBottom: 12,
          transition: 'all 200ms ease'
        }}
        onMouseEnter={e => { if (activeSession !== -1) e.currentTarget.style.background = '#F9F9F9' }}
        onMouseLeave={e => { if (activeSession !== -1) e.currentTarget.style.background = 'transparent' }}
      >
        <span style={{ fontSize: 14, fontWeight: activeSession === -1 ? 700 : 500, color: 'var(--ink)' }}>Course Overview</span>
      </button>

      {Object.entries(byWeek).map(([week, rows]) => (
        <div key={week} style={{ marginBottom: 16 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink-faint)', margin: '0 20px 8px' }}>
            Week {week}
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {rows.map(s => {
              const idx = sessions.indexOf(s)
              const on  = activeSession === idx
              return (
                <button
                  key={idx}
                  onClick={() => onSelect(idx)}
                  style={{
                    width: '100%', textAlign: 'left', padding: '8px 20px',
                    background: on ? '#FAFAF8' : 'transparent',
                    border: 'none', borderLeft: `3px solid ${on ? 'var(--ink)' : 'transparent'}`,
                    cursor: 'pointer', fontFamily: 'var(--font-sans)',
                    transition: 'all 200ms ease'
                  }}
                  onMouseEnter={e => { if (!on) e.currentTarget.style.background = '#F9F9F9' }}
                  onMouseLeave={e => { if (!on) e.currentTarget.style.background = 'transparent' }}
                >
                  <span style={{ fontSize: 11, fontWeight: 600, color: on ? 'var(--ink)' : 'var(--ink-faint)', display: 'block', marginBottom: 2 }}>
                    Session {s.session}
                  </span>
                  <span style={{ fontSize: 13, fontWeight: on ? 600 : 400, color: 'var(--ink)', lineHeight: 1.3, display: 'block' }}>
                    {s.topic}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </aside>
  )
}
