import ReactMarkdown from 'react-markdown'

export function Markdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        h1: ({ ...props }) => <h1 style={{ fontSize: 22, fontWeight: 700, margin: '24px 0 12px', color: 'var(--ink)' }} {...props} />,
        h2: ({ ...props }) => <h2 style={{ fontSize: 18, fontWeight: 700, margin: '20px 0 10px', color: 'var(--ink)' }} {...props} />,
        h3: ({ ...props }) => <h3 style={{ fontSize: 16, fontWeight: 700, margin: '16px 0 8px', color: 'var(--ink)' }} {...props} />,
        h4: ({ ...props }) => <h4 style={{ fontSize: 14, fontWeight: 700, margin: '12px 0 6px', color: 'var(--ink)' }} {...props} />,
        p: ({ ...props }) => <p style={{ fontSize: 14, color: 'var(--ink)', lineHeight: 1.6, margin: '0 0 12px' }} {...props} />,
        ul: ({ ...props }) => <ul style={{ fontSize: 14, color: 'var(--ink)', lineHeight: 1.6, margin: '0 0 12px 20px', padding: 0 }} {...props} />,
        ol: ({ ...props }) => <ol style={{ fontSize: 14, color: 'var(--ink)', lineHeight: 1.6, margin: '0 0 12px 20px', padding: 0 }} {...props} />,
        li: ({ ...props }) => <li style={{ marginBottom: 4 }} {...props} />,
        strong: ({ ...props }) => <strong style={{ fontWeight: 700, color: 'var(--ink)' }} {...props} />,
        em: ({ ...props }) => <em style={{ fontStyle: 'italic' }} {...props} />,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
