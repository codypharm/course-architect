import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

/* ─── Inline SVG icon primitives (no emoji, no icon library needed) ─── */
function Icon({ path, size = 18 }: { path: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={path} />
    </svg>
  )
}

const ICONS = {
  message:    'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
  check:      'M9 12l2 2 4-4M22 12A10 10 0 1 1 2 12a10 10 0 0 1 20 0z',
  user:       'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  book:       'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15z',
  grid:       'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z',
  refresh:    'M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15',
  arrow:      'M5 12h14M12 5l7 7-7 7',
  play:       'M5 3l14 9-14 9V3z',
}

/* ─── Scroll-triggered fade-in hook ─── */
function useVisible(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ob = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true) }, { threshold })
    ob.observe(el)
    return () => ob.disconnect()
  }, [threshold])
  return { ref, visible }
}

/* ─── Generation steps shown from the educator's perspective ─── */
const GEN_STEPS = [
  { id: 'read',    label: 'Reading your uploaded materials' },
  { id: 'check',   label: 'Checking feasibility & content gaps' },
  { id: 'plan',    label: 'Planning a 6-week session schedule' },
  { id: 'write',   label: 'Writing lesson content & scripts' },
  { id: 'quiz',    label: 'Generating quizzes & worksheets' },
]

const SAMPLE_SESSIONS = [
  { week: 1, session: 1, topic: 'Variables, Types & First Programs',  formats: ['Lesson', 'Quiz'] },
  { week: 1, session: 2, topic: 'Control Flow — if / else and Loops', formats: ['Lesson', 'Worksheet'] },
  { week: 2, session: 1, topic: 'Functions and Scope',                formats: ['Lesson', 'Script', 'Quiz'] },
]

/**
 * Shows the educator what's happening in plain language,
 * then reveals a sample of the finished course output.
 */
function CoursePreviewCard() {
  const [phase, setPhase] = useState<'building' | 'ready'>('building')
  const [activeStep, setActiveStep] = useState(0)

  useEffect(() => {
    let step = 0
    let readyTimer: ReturnType<typeof setTimeout> | null = null

    function startCycle() {
      step = 0
      setActiveStep(0)
      setPhase('building')

      const t = setInterval(() => {
        step += 1
        if (step < GEN_STEPS.length) {
          setActiveStep(step)
        } else {
          clearInterval(t)
          setPhase('ready')
          // Hold the result view for 2.5 s then restart
          readyTimer = setTimeout(startCycle, 2500)
        }
      }, 900)

      return t
    }

    const first = startCycle()
    return () => {
      clearInterval(first)
      if (readyTimer) clearTimeout(readyTimer)
    }
  }, [])

  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        overflow: 'hidden',
        maxWidth: 420,
      }}
    >
      {/* Card header */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border)',
          background: '#F7F6F3',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <div>
          <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', margin: '0 0 2px' }}>
            Introduction to Python
          </p>
          <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: 0 }}>
            Ages 15–17 · 6 weeks · 18 sessions
          </p>
        </div>
        <span
          style={{
            fontSize: 10,
            fontWeight: 500,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            padding: '3px 10px',
            borderRadius: 9999,
            background: phase === 'ready' ? 'var(--accent-green-bg)'  : 'var(--accent-yellow-bg)',
            color:      phase === 'ready' ? 'var(--accent-green-text)' : 'var(--accent-yellow-text)',
          }}
        >
          {phase === 'ready' ? 'Ready' : 'Building…'}
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: '16px 20px' }}>
        {phase === 'building' ? (
          /* ── Progress view ── */
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {GEN_STEPS.map((s, i) => {
              const isDone   = i < activeStep
              const isActive = i === activeStep
              return (
                <div
                  key={s.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '7px 10px',
                    borderRadius: 6,
                    background: isActive ? '#F7F6F3' : 'transparent',
                    transition: 'background 250ms',
                  }}
                >
                  {/* Circle indicator */}
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: '50%',
                      flexShrink: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: isDone
                        ? 'var(--accent-green-bg)'
                        : isActive
                          ? 'var(--accent-yellow-bg)'
                          : '#F7F6F3',
                      border: isDone || isActive ? 'none' : '1px solid var(--border)',
                      transition: 'background 250ms',
                    }}
                  >
                    {isDone && (
                      <svg width="9" height="9" viewBox="0 0 12 12" fill="none">
                        <path d="M2 6l3 3 5-5" stroke="var(--accent-green-text)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                    {isActive && (
                      <div
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: 'var(--accent-yellow-text)',
                          animation: 'pulse 1s ease infinite',
                        }}
                      />
                    )}
                  </div>

                  <span
                    style={{
                      fontSize: 13,
                      color: isDone ? 'var(--ink-faint)' : isActive ? 'var(--ink)' : 'var(--ink-muted)',
                      fontWeight: isActive ? 500 : 400,
                    }}
                  >
                    {s.label}
                  </span>
                </div>
              )
            })}

            {/* Progress bar */}
            <div
              style={{
                marginTop: 12,
                height: 3,
                borderRadius: 2,
                background: '#EAEAEA',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  borderRadius: 2,
                  background: 'var(--ink)',
                  width: `${((activeStep + 1) / GEN_STEPS.length) * 100}%`,
                  transition: 'width 600ms cubic-bezier(0.16,1,0.3,1)',
                }}
              />
            </div>
          </div>
        ) : (
          /* ── Output preview view ── */
          <div>
            <p
              style={{ fontSize: 11, color: 'var(--ink-faint)', textTransform: 'uppercase', letterSpacing: '0.07em', margin: '0 0 10px' }}
            >
              Your course is ready
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {SAMPLE_SESSIONS.map((s, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '9px 12px',
                    background: '#F7F6F3',
                    borderRadius: 7,
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      color: 'var(--ink-faint)',
                      width: 32,
                      flexShrink: 0,
                    }}
                  >
                    W{s.week}·S{s.session}
                  </span>
                  <span style={{ fontSize: 13, color: 'var(--ink)', flex: 1 }}>{s.topic}</span>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {s.formats.map(f => (
                      <span
                        key={f}
                        style={{
                          fontSize: 10,
                          padding: '2px 7px',
                          borderRadius: 9999,
                          background: 'var(--accent-blue-bg)',
                          color: 'var(--accent-blue-text)',
                          fontWeight: 500,
                        }}
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              <p style={{ fontSize: 12, color: 'var(--ink-faint)', textAlign: 'center', margin: '4px 0 0' }}>
                + 15 more sessions
              </p>
            </div>

            {/* Output stats */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 8,
                marginTop: 14,
                paddingTop: 14,
                borderTop: '1px solid var(--border)',
              }}
            >
              {[{ v: '18', l: 'Sessions' }, { v: '54', l: 'Content items' }, { v: '36h', l: 'Est. hours' }].map(s => (
                <div key={s.l} style={{ textAlign: 'center' }}>
                  <p className="serif" style={{ fontSize: 22, color: 'var(--ink)', margin: '0 0 2px' }}>{s.v}</p>
                  <p style={{ fontSize: 11, color: 'var(--ink-faint)', margin: 0 }}>{s.l}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── Feature card (bento) ─── */
function FeatureCard({
  icon, title, body, delay = '0s',
}: {
  icon: string
  title: string
  body: string
  delay?: string
}) {
  const { ref, visible } = useVisible()
  return (
    <div
      ref={ref}
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '28px 32px',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(12px)',
        transition: `opacity 600ms cubic-bezier(0.16,1,0.3,1) ${delay}, transform 600ms cubic-bezier(0.16,1,0.3,1) ${delay}`,
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 8,
          background: '#F7F6F3',
          border: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 20,
          color: 'var(--ink-muted)',
        }}
      >
        <Icon path={icon} size={16} />
      </div>
      <h3
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 15,
          fontWeight: 600,
          color: 'var(--ink)',
          margin: '0 0 8px',
        }}
      >
        {title}
      </h3>
      <p style={{ fontSize: 14, color: 'var(--ink-muted)', lineHeight: 1.6, margin: 0 }}>
        {body}
      </p>
    </div>
  )
}

/* ─── How-it-works step ─── */
function HowStep({
  n, title, body, delay = '0s',
}: {
  n: string; title: string; body: string; delay?: string
}) {
  const { ref, visible } = useVisible()
  return (
    <div
      ref={ref}
      style={{
        display: 'grid',
        gridTemplateColumns: '28px 1fr',
        gap: '0 20px',
        paddingBottom: 28,
        borderBottom: '1px solid var(--border)',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(12px)',
        transition: `opacity 600ms cubic-bezier(0.16,1,0.3,1) ${delay}, transform 600ms cubic-bezier(0.16,1,0.3,1) ${delay}`,
      }}
    >
      <span
        className="mono"
        style={{ fontSize: 12, color: 'var(--ink-faint)', paddingTop: 3 }}
      >
        {n}
      </span>
      <div>
        <p style={{ fontWeight: 600, fontSize: 15, color: 'var(--ink)', margin: '0 0 6px' }}>{title}</p>
        <p style={{ fontSize: 14, color: 'var(--ink-muted)', lineHeight: 1.6, margin: 0 }}>{body}</p>
      </div>
    </div>
  )
}

/* ─── Main landing page ─── */
export default function LandingPage() {
  return (
    <div style={{ background: 'var(--canvas)', minHeight: '100vh' }}>
      {/* Ambient background blob */}
      <div className="ambient-blob" aria-hidden />

      {/* ── Navbar ── */}
      <nav
        className="px-page"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 50,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 56,
          background: 'rgba(251,251,250,0.85)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--border)',
          fontFamily: 'var(--font-sans)',
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="var(--ink)">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', letterSpacing: '-0.01em' }}>
            Course Architect
          </span>
        </div>

        {/* Links — hidden on mobile */}
        <div className="nav-links" style={{ gap: 32 }}>
          {['Features', 'How it works'].map(l => (
            <a
              key={l}
              href={`#${l.toLowerCase().replace(/\s/g, '-')}`}
              style={{ fontSize: 14, color: 'var(--ink-muted)', textDecoration: 'none' }}
            >
              {l}
            </a>
          ))}
        </div>

        {/* CTA */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Link to="/dashboard" style={{ fontSize: 14, color: 'var(--ink-muted)', textDecoration: 'none' }}>
            Sign in
          </Link>
          <Link
            to="/dashboard"
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: '#fff',
              background: 'var(--ink)',
              padding: '7px 16px',
              borderRadius: 5,
              textDecoration: 'none',
              transition: 'background 150ms',
            }}
          >
            Get started
          </Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section
        className="hero-grid px-page"
        style={{
          maxWidth: 1100,
          margin: '0 auto',
          paddingTop: 110,
          paddingBottom: 72,
          alignItems: 'center',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Left */}
        <div>
          {/* Pill tag */}
          <span
            className="enter"
            style={{
              display: 'inline-block',
              fontSize: 11,
              fontWeight: 500,
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
              padding: '4px 12px',
              borderRadius: 9999,
              background: 'var(--accent-blue-bg)',
              color: 'var(--accent-blue-text)',
              marginBottom: 28,
              animationDelay: '0s',
            }}
          >
            AI-powered curriculum generation
          </span>

          {/* Headline */}
          <h1
            className="serif enter"
            style={{
              fontSize: 'clamp(42px, 5vw, 64px)',
              fontWeight: 400,
              color: 'var(--ink)',
              margin: '0 0 24px',
              animationDelay: '80ms',
            }}
          >
            Transform your expertise into complete curricula.
          </h1>

          {/* Sub */}
          <p
            className="enter"
            style={{
              fontSize: 16,
              color: 'var(--ink-muted)',
              lineHeight: 1.7,
              maxWidth: 460,
              margin: '0 0 40px',
              animationDelay: '160ms',
            }}
          >
            Upload your knowledge base, describe your audience, and receive a full
            structured course — sessions, quizzes, scripts, and worksheets — in minutes.
          </p>

          {/* CTA row */}
          <div className="enter" style={{ display: 'flex', gap: 12, alignItems: 'center', animationDelay: '240ms' }}>
            <Link
              to="/dashboard"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 14,
                fontWeight: 500,
                color: '#fff',
                background: 'var(--ink)',
                padding: '10px 22px',
                borderRadius: 5,
                textDecoration: 'none',
              }}
            >
              Start generating for free
              <Icon path={ICONS.arrow} size={14} />
            </Link>
            <button
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 14,
                color: 'var(--ink-muted)',
                background: 'transparent',
                border: '1px solid var(--border)',
                padding: '10px 20px',
                borderRadius: 5,
                cursor: 'pointer',
              }}
            >
              <Icon path={ICONS.play} size={13} />
              Watch demo
            </button>
          </div>

          {/* Social proof */}
          <div
            className="enter"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              marginTop: 40,
              animationDelay: '320ms',
            }}
          >
            {/* Avatar strip */}
            <div style={{ display: 'flex' }}>
              {['#E1F3FE', '#EDF3EC', '#FBF3DB', '#FDEBEC', '#F7F6F3'].map((c, i) => (
                <div
                  key={i}
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    background: c,
                    border: '2px solid var(--canvas)',
                    marginLeft: i === 0 ? 0 : -8,
                  }}
                />
              ))}
            </div>
            <p style={{ fontSize: 13, color: 'var(--ink-muted)', margin: 0 }}>
              Joined by <strong style={{ color: 'var(--ink)', fontWeight: 600 }}>10,000+</strong> educators
            </p>
          </div>
        </div>

        {/* Right — pipeline visualization */}
        <div className="enter" style={{ animationDelay: '120ms' }}>
          <CoursePreviewCard />
        </div>
      </section>

      {/* ── Stats bar ── */}
      <div style={{ borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
        <div
          className="stats-grid px-page"
          style={{ maxWidth: 1100, margin: '0 auto' }}
        >
          {[
            { value: '10,000+', label: 'educators worldwide' },
            { value: '250K+',   label: 'courses generated' },
            { value: '< 5 min', label: 'avg. generation time' },
            { value: '98.4%',   label: 'satisfaction rate' },
          ].map((s, i) => (
            <div
              key={s.label}
              style={{
                padding: '28px 0',
                textAlign: 'center',
                borderLeft: i > 0 ? '1px solid var(--border)' : 'none',
              }}
            >
              <p
                className="serif"
                style={{ fontSize: 28, color: 'var(--ink)', margin: '0 0 4px' }}
              >
                {s.value}
              </p>
              <p style={{ fontSize: 13, color: 'var(--ink-muted)', margin: 0 }}>{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Features bento ── */}
      <section
        id="features"
        className="px-page"
        style={{ maxWidth: 1100, margin: '0 auto', padding: '72px 0' }}
      >
        {/* Heading */}
        <div style={{ maxWidth: 560, marginBottom: 56 }}>
          <p
            className="mono"
            style={{ fontSize: 11, color: 'var(--ink-faint)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}
          >
            What you get
          </p>
          <h2 className="serif" style={{ fontSize: 40, color: 'var(--ink)', margin: '0 0 16px' }}>
            Every layer of your course, handled.
          </h2>
          <p style={{ fontSize: 15, color: 'var(--ink-muted)', lineHeight: 1.65, margin: 0 }}>
            A multi-agent pipeline that writes what takes weeks — in minutes.
          </p>
        </div>

        {/* Asymmetric bento grid */}
        <div className="bento-grid">
          {/* Wide card */}
          <div
            className="bento-wide"
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: '32px 36px',
            }}
          >
            <div
              style={{
                width: 36, height: 36, borderRadius: 8,
                background: '#F7F6F3', border: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 20, color: 'var(--ink-muted)',
              }}
            >
              <Icon path={ICONS.user} size={16} />
            </div>
            <h3 style={{ fontFamily: 'var(--font-sans)', fontSize: 15, fontWeight: 600, color: 'var(--ink)', margin: '0 0 10px' }}>
              Human-in-the-Loop checkpoints
            </h3>
            <p style={{ fontSize: 14, color: 'var(--ink-muted)', lineHeight: 1.65, margin: '0 0 20px' }}>
              You stay in control. The pipeline pauses twice — once after validation, once after curriculum planning —
              to surface flags, cost estimates, and the full session schedule before proceeding. Approve or revise with a single click.
            </p>
            {/* Inline preview of the HITL checkpoint UI */}
            <div
              style={{
                background: '#F7F6F3',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '14px 18px',
              }}
            >
              <p
                className="mono"
                style={{ fontSize: 11, color: 'var(--ink-faint)', margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.06em' }}
              >
                Pre-flight report
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { label: 'Age appropriateness', status: 'pass', badge: 'green' },
                  { label: 'Knowledge base depth', status: 'pass', badge: 'green' },
                  { label: 'Duration feasibility',  status: 'flag', badge: 'yellow' },
                ].map(row => (
                  <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>{row.label}</span>
                    <span
                      style={{
                        fontSize: 10, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase',
                        padding: '2px 8px', borderRadius: 9999,
                        background: row.badge === 'green' ? 'var(--accent-green-bg)' : 'var(--accent-yellow-bg)',
                        color:      row.badge === 'green' ? 'var(--accent-green-text)' : 'var(--accent-yellow-text)',
                      }}
                    >
                      {row.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <FeatureCard icon={ICONS.message} title="Conversational intake" body="The Intake Agent probes vague answers before passing the brief to the pipeline — no incomplete state enters generation." delay="0s" />
          <FeatureCard icon={ICONS.check}   title="Feasibility validation" body="Age-appropriateness, knowledge-base depth, duration feasibility, and estimated token cost — checked before a word is generated." delay="80ms" />
          <FeatureCard icon={ICONS.book}    title="RAG-backed generation" body="Content agents retrieve only the relevant knowledge-base chunks per session. The full corpus never inflates the context window." delay="160ms" />
          <FeatureCard icon={ICONS.refresh} title="Retry with hard constraints" body="Add refinement context — 'shorter', 'more practical' — and the curriculum re-generates from the planner, honouring every prior constraint." delay="240ms" />
        </div>
      </section>

      {/* ── How it works ── */}
      <section
        id="how-it-works"
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        <div
          className="how-grid px-page"
          style={{
            maxWidth: 1100,
            margin: '0 auto',
            paddingTop: 72,
            paddingBottom: 72,
          }}
        >
          {/* Left */}
          <div>
            <p
              className="mono"
              style={{ fontSize: 11, color: 'var(--ink-faint)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}
            >
              How it works
            </p>
            <h2
              className="serif"
              style={{ fontSize: 40, color: 'var(--ink)', margin: '0 0 48px' }}
            >
              From brief to complete course in four steps.
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
              <HowStep n="01" title="Upload your knowledge base" body="PDFs, notes, URLs — everything you know about the subject. The pipeline treats it as the single source of truth." delay="0s" />
              <HowStep n="02" title="Configure the course brief" body="Subject, audience age, duration, sessions per week, preferred formats. The Intake Agent will ask if anything's missing." delay="80ms" />
              <HowStep n="03" title="Approve the pre-flight report" body="Review flags, suggestions, and estimated cost. Click approve and step back — the pipeline does the rest." delay="160ms" />
              <HowStep n="04" title="Receive your course pack" body="Session schedule, lesson content, video scripts, quizzes, and worksheets — age-calibrated and ready to use." delay="240ms" />
            </div>
          </div>

          {/* Right — sample output */}
          <div style={{ alignSelf: 'start', position: 'sticky', top: 80 }}>
            <div
              className="os-window"
              style={{ background: 'var(--surface)' }}
            >
              <div className="os-titlebar">
                <span className="os-dot" />
                <span className="os-dot" />
                <span className="os-dot" />
                <span className="mono" style={{ fontSize: 11, color: 'var(--ink-faint)', marginLeft: 6 }}>
                  course-output.json
                </span>
              </div>
              <div style={{ padding: '20px 24px' }}>
                <div style={{ marginBottom: 16 }}>
                  <p className="mono" style={{ fontSize: 11, color: 'var(--ink-faint)', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Sample output
                  </p>
                  <p style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)', margin: '0 0 2px' }}>
                    Introduction to Python · Ages 15–17 · 6 Weeks
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--ink-faint)', margin: 0 }}>
                    3 sessions / week · 18 sessions total
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {[
                    { week: 1, topic: 'Variables, Types & First Programs',    formats: ['lesson', 'quiz'] },
                    { week: 1, topic: 'Control Flow — if / else and Loops',   formats: ['lesson', 'worksheet'] },
                    { week: 2, topic: 'Functions and Scope',                   formats: ['lesson', 'script', 'quiz'] },
                    { week: 2, topic: 'Lists, Tuples & Dictionaries',         formats: ['lesson', 'worksheet'] },
                    { week: 3, topic: 'File I/O and Error Handling',          formats: ['lesson', 'quiz'] },
                  ].map((s, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '8px 12px',
                        background: '#F7F6F3',
                        borderRadius: 6,
                      }}
                    >
                      <span
                        className="mono"
                        style={{ fontSize: 10, color: 'var(--ink-faint)', width: 18, flexShrink: 0 }}
                      >
                        W{s.week}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--ink)', flex: 1 }}>{s.topic}</span>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {s.formats.map(f => (
                          <span
                            key={f}
                            style={{
                              fontSize: 10, fontWeight: 500, letterSpacing: '0.04em',
                              padding: '1px 6px', borderRadius: 9999,
                              background: 'var(--accent-blue-bg)', color: 'var(--accent-blue-text)',
                            }}
                          >
                            {f}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                  <p className="mono" style={{ fontSize: 11, color: 'var(--ink-faint)', textAlign: 'center', margin: '4px 0 0' }}>
                    + 13 more sessions
                  </p>
                </div>

                {/* Stats row */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: 8,
                    marginTop: 16,
                    paddingTop: 16,
                    borderTop: '1px solid var(--border)',
                  }}
                >
                  {[
                    { v: '18',  l: 'sessions' },
                    { v: '54',  l: 'content items' },
                    { v: '36h', l: 'est. hours' },
                  ].map(s => (
                    <div key={s.l} style={{ textAlign: 'center' }}>
                      <p className="serif" style={{ fontSize: 22, color: 'var(--ink)', margin: '0 0 2px' }}>{s.v}</p>
                      <p style={{ fontSize: 11, color: 'var(--ink-faint)', margin: 0 }}>{s.l}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--canvas)',
        }}
      >
        <div
          style={{
            maxWidth: 1100,
            margin: '0 auto',
            paddingTop: 72,
            paddingBottom: 72,
            textAlign: 'center',
          }}
        >
          <p
            className="mono"
            style={{ fontSize: 11, color: 'var(--ink-faint)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 20 }}
          >
            Ready to build?
          </p>
          <h2
            className="serif"
            style={{ fontSize: 'clamp(32px, 4vw, 52px)', color: 'var(--ink)', margin: '0 0 20px' }}
          >
            Your next course is waiting to be generated.
          </h2>
          <p style={{ fontSize: 15, color: 'var(--ink-muted)', margin: '0 0 40px' }}>
            No credit card required. Start with your first course, free.
          </p>
          <Link
            to="/dashboard"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 14,
              fontWeight: 500,
              color: '#fff',
              background: 'var(--ink)',
              padding: '12px 28px',
              borderRadius: 5,
              textDecoration: 'none',
            }}
          >
            Start generating for free
            <Icon path={ICONS.arrow} size={14} />
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer
        className="px-page"
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--surface)',
          paddingTop: 24,
          paddingBottom: 24,
        }}
      >
        <div
          style={{
            maxWidth: 1100,
            margin: '0 auto',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={{ fontSize: 13, color: 'var(--ink-faint)' }}>
            Course Architect © 2026
          </span>
          <div style={{ display: 'flex', gap: 28 }}>
            {['Privacy', 'Terms', 'Contact'].map(l => (
              <a key={l} href="#" style={{ fontSize: 13, color: 'var(--ink-faint)', textDecoration: 'none' }}>
                {l}
              </a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  )
}
