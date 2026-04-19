import { type SessionPlan } from '@/types/course'
import { QuizCard } from './QuizCard'
import { Ico, I } from '@/components/Icon'

export function SessionPanel({ session }: { session: SessionPlan }) {
  return (
    <div style={{ animation: 'enter 300ms ease' }}>
      {/* Title Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32, paddingBottom: 24, borderBottom: '1px solid var(--border)' }}>
        <div>
          <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink-muted)', margin: '0 0 6px' }}>
            Week {session.week} · Session {session.session}
          </p>
          <h2 className="serif" style={{ fontSize: 32, color: 'var(--ink)', margin: 0, letterSpacing: '-0.02em', lineHeight: 1.2 }}>
            {session.topic}
          </h2>
        </div>
      </div>

      {/* Objectives */}
      {session.objectives.length > 0 && (
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Ico d={I.check} size={16} color="var(--ink-muted)" />
            <h3 style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink)', margin: 0 }}>
              Learning Objectives
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {session.objectives.map((o, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 16px', background: '#FAFAF8', borderRadius: 8, borderLeft: '3px solid var(--ink)' }}>
                <span style={{ fontSize: 14, color: 'var(--ink)', lineHeight: 1.5 }}>{o}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lesson outline */}
      {session.lesson_outline.length > 0 && (
        <div style={{ marginBottom: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Ico d={I.book} size={16} color="var(--ink-muted)" />
            <h3 style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink)', margin: 0 }}>
              Lesson Outline
            </h3>
          </div>
          <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '24px 32px' }}>
            <ol style={{ margin: 0, padding: 0, listStylePosition: 'inside', display: 'flex', flexDirection: 'column', gap: 16 }}>
              {session.lesson_outline.map((point, i) => (
                <li key={i} style={{ fontSize: 15, color: 'var(--ink)', lineHeight: 1.7 }}>
                  <span style={{ marginLeft: 8 }}>{point}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {/* Quiz */}
      {session.quiz_questions.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Ico d={I.layers} size={16} color="var(--ink-muted)" />
            <h3 style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink)', margin: 0 }}>
              Knowledge Check — {session.quiz_questions.length} Question{session.quiz_questions.length !== 1 ? 's' : ''}
            </h3>
          </div>
          <div>
            {session.quiz_questions.map((q, i) => <QuizCard key={i} q={q} idx={i} />)}
          </div>
        </div>
      )}
    </div>
  )
}
