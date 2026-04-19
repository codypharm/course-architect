import { type CurriculumPlan, type SessionPlan } from '@/types/course'
import { Ico, I } from '@/components/Icon'

interface CourseOverviewProps {
  plan: CurriculumPlan
  sessions: SessionPlan[]
  byWeek: Record<number, SessionPlan[]>
}

export function CourseOverview({ plan, sessions, byWeek }: CourseOverviewProps) {
  const totalQuestions = sessions.reduce((acc, s) => acc + s.quiz_questions.length, 0)
  const totalWeeks = Object.keys(byWeek).length

  return (
    <div style={{ animation: 'enter 400ms ease' }}>
      <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 16, padding: '32px', marginBottom: 24, boxShadow: '0 4px 12px rgba(0,0,0,0.02)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--ink)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Ico d={I.book} size={16} color="#fff" />
          </div>
          <p style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: 0 }}>
            Course Overview
          </p>
        </div>
        
        <p style={{ fontSize: 16, color: 'var(--ink)', lineHeight: 1.7, margin: '0 0 32px' }}>
          {plan.course_overview}
        </p>

        {/* Bento Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
          <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 12, padding: '20px' }}>
            <Ico d={I.layers} size={18} color="var(--ink-muted)" style={{ marginBottom: 16 }} />
            <p style={{ fontSize: 12, color: 'var(--ink-faint)', margin: '0 0 4px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Sessions</p>
            <p style={{ fontSize: 24, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>{sessions.length}</p>
          </div>

          <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 12, padding: '20px' }}>
            <Ico d={I.calendar} size={18} color="var(--ink-muted)" style={{ marginBottom: 16 }} />
            <p style={{ fontSize: 12, color: 'var(--ink-faint)', margin: '0 0 4px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Duration</p>
            <p style={{ fontSize: 24, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>{totalWeeks} Weeks</p>
          </div>

          {totalQuestions > 0 && (
            <div style={{ background: '#FAFAF8', border: '1px solid var(--border)', borderRadius: 12, padding: '20px' }}>
              <Ico d={I.check} size={18} color="var(--ink-muted)" style={{ marginBottom: 16 }} />
              <p style={{ fontSize: 12, color: 'var(--ink-faint)', margin: '0 0 4px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Quiz Questions</p>
              <p style={{ fontSize: 24, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>{totalQuestions}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
