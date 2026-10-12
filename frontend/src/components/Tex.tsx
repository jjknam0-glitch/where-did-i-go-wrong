import katex from 'katex'
import { memo, useMemo } from 'react'

function render(latex: string, display: boolean): string | null {
  try {
    return katex.renderToString(latex, { throwOnError: true, displayMode: display, strict: 'ignore', output: 'html' })
  } catch {
    return null
  }
}

/** Rendered LaTeX; falls back to the raw text if it can't be rendered. */
export const Tex = memo(function Tex({ latex, display = false, className = '' }: { latex: string; display?: boolean; className?: string }) {
  const html = useMemo(() => (latex ? render(latex, display) : ''), [latex, display])
  if (html === null) return <code className={`font-mono text-[0.9em] ${className}`}>{latex}</code>
  return <span className={`math ${className}`} dangerouslySetInnerHTML={{ __html: html }} />
})

/** Plain text with $...$ math segments. */
export const TexText = memo(function TexText({ text, className = '' }: { text: string; className?: string }) {
  const parts = useMemo(() => {
    const out: { math: boolean; s: string }[] = []
    const re = /\$([^$]+)\$/g
    let last = 0
    let m: RegExpExecArray | null
    while ((m = re.exec(text))) {
      if (m.index > last) out.push({ math: false, s: text.slice(last, m.index) })
      out.push({ math: true, s: m[1] })
      last = m.index + m[0].length
    }
    if (last < text.length) out.push({ math: false, s: text.slice(last) })
    return out
  }, [text])
  return (
    <span className={className}>
      {parts.map((p, i) => (p.math ? <Tex key={i} latex={p.s} /> : <span key={i}>{renderEmphasis(p.s)}</span>))}
    </span>
  )
})

function renderEmphasis(s: string) {
  // *word* -> italics (used in lesson text)
  const pieces = s.split(/(\*[^*]+\*)/g)
  return pieces.map((p, i) => (p.startsWith('*') && p.endsWith('*') && p.length > 2 ? <em key={i}>{p.slice(1, -1)}</em> : p))
}
