import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Tex } from './Tex'
import { inputClass } from './ui'

export interface ParsedPreview {
  latex: string | null
  error: string | null
}

const cache = new Map<string, ParsedPreview>()

/** Parse lines on the server (the same parser the checker uses), with a small cache. */
export async function parseLines(lines: string[]): Promise<ParsedPreview[]> {
  const missing = [...new Set(lines.filter((l) => l.trim() && !cache.has(l)))]
  if (missing.length) {
    const res = await api.parse(missing)
    missing.forEach((l, i) => cache.set(l, res.lines[i] ?? { latex: null, error: 'Unknown' }))
  }
  return lines.map((l) => (l.trim() ? cache.get(l) ?? { latex: null, error: null } : { latex: '', error: null }))
}

export function useParsed(text: string, delay = 300): ParsedPreview & { pending: boolean } {
  const [value, setValue] = useState<ParsedPreview>(() => cache.get(text) ?? { latex: null, error: null })
  const [pending, setPending] = useState(false)
  useEffect(() => {
    if (!text.trim()) {
      setValue({ latex: '', error: null })
      setPending(false)
      return
    }
    const hit = cache.get(text)
    if (hit) {
      setValue(hit)
      setPending(false)
      return
    }
    setPending(true)
    let alive = true
    const t = setTimeout(() => {
      parseLines([text])
        .then(([p]) => alive && setValue(p))
        .catch(() => alive && setValue({ latex: null, error: null }))
        .finally(() => alive && setPending(false))
    }, delay)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [text, delay])
  return { ...value, pending }
}

export function MathPreview({ text, className = '' }: { text: string; className?: string }) {
  const p = useParsed(text)
  if (!text.trim()) return <span className="text-sm text-faint">Nothing yet</span>
  if (p.latex) return <span className={`math-scroll block ${className}`}><Tex latex={p.latex} /></span>
  if (p.error) return <span className="text-sm text-pen">{p.error}</span>
  return <span className="font-mono text-sm text-muted">{text}</span>
}

export function MathInput({ value, onChange, onSubmit, placeholder = 'e.g. 2x + 3 = 7', autoFocus = false, label, id }:
  { value: string; onChange: (v: string) => void; onSubmit?: () => void; placeholder?: string; autoFocus?: boolean; label: string; id?: string }) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (autoFocus) ref.current?.focus()
  }, [autoFocus])
  return (
    <div>
      <input
        id={id}
        ref={ref}
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && onSubmit) {
            e.preventDefault()
            onSubmit()
          }
        }}
        placeholder={placeholder}
        autoComplete="off"
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        inputMode="text"
        className={`${inputClass} font-mono`}
        maxLength={300}
      />
      <div className="mt-2 min-h-7 rounded-xl bg-surface-2/60 px-3 py-1.5" aria-live="polite">
        <MathPreview text={value} />
      </div>
    </div>
  )
}

export const SYNTAX_TIPS = [
  ['x^2', 'powers'],
  ['(x+1)/2', 'fractions'],
  ['sqrt(x)', 'roots'],
  ["f'(x) = …", 'derivatives'],
  ['∫ 2x dx', 'integrals (or int 2x dx)'],
  ['x = 2 or x = -3', 'several answers'],
]
