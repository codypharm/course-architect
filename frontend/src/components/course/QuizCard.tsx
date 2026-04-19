import { useState } from 'react'
import { type QuizQuestion } from '@/types/course'

export function QuizCard({ q, idx }: { q: QuizQuestion; idx: number }) {
  const [revealed, setRevealed] = useState(false)

  return (
    <div style={{ background: '#FAFAF8', borderRadius: 12, padding: '20px', marginBottom: 16, border: '1px solid var(--border)' }}>
      <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink)', margin: '0 0 16px', lineHeight: 1.5 }}>
        <span style={{ color: 'var(--ink-muted)', marginRight: 6 }}>{idx + 1}.</span>
        {q.question}
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
        {q.options.map((opt, i) => {
          const isCorrect = revealed && opt === q.answer
          const isSelectedAndWrong = revealed && !isCorrect // Optionally we could track user selection, but here we just show the correct answer upon reveal.
          const letter = ['A', 'B', 'C', 'D'][i]
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
              borderRadius: 8, border: `1px solid ${isCorrect ? 'var(--accent-green-text)' : 'var(--border)'}`,
              background: isCorrect ? 'var(--accent-green-bg)' : '#fff', transition: 'all 200ms',
              boxShadow: '0 1px 2px rgba(0,0,0,0.02)'
            }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: isCorrect ? 'var(--accent-green-text)' : 'var(--ink-muted)', minWidth: 20 }}>
                {letter}
              </span>
              <span style={{ fontSize: 14, color: isCorrect ? 'var(--accent-green-text)' : 'var(--ink)' }}>
                {opt}
              </span>
            </div>
          )
        })}
      </div>
      {revealed ? (
        <div style={{ animation: 'enter 300ms ease', background: '#fff', padding: '16px', borderRadius: 8, border: '1px solid var(--border)', borderLeft: '4px solid var(--ink)' }}>
          <p style={{ fontSize: 13, color: 'var(--ink)', margin: 0, lineHeight: 1.5 }}>
            <strong style={{ fontWeight: 700, marginRight: 6 }}>Explanation:</strong> 
            {q.explanation}
          </p>
        </div>
      ) : (
        <button
          onClick={() => setRevealed(true)}
          style={{ fontSize: 13, fontWeight: 600, color: '#fff', background: 'var(--ink)', border: 'none', borderRadius: 8, padding: '10px 20px', cursor: 'pointer', fontFamily: 'var(--font-sans)', transition: 'opacity 200ms', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}
          onMouseEnter={e => e.currentTarget.style.opacity = '0.9'}
          onMouseLeave={e => e.currentTarget.style.opacity = '1'}
        >
          Check Answer
        </button>
      )}
    </div>
  )
}
