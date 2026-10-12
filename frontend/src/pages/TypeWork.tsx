import { Plus, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { MathInput, parseLines, SYNTAX_TIPS } from '../components/MathInput'
import { Button, ErrorNote, PageHeader } from '../components/ui'
import { blankDraft, newSession } from '../lib/flow'
import { checksLeftToday } from '../lib/profile'
import { useStore } from '../lib/store'
import { useRunCheck } from '../lib/useRunCheck'

function starter(problem: string | null, kind: string | null): { lines: string[]; placeholders: string[]; title?: string } {
  if (!problem) return { lines: ['', '', ''], placeholders: ['e.g. 2x + 3 = 7', 'e.g. 2x = 4', 'e.g. x = 2'] }
  if (kind === 'differentiate') return { lines: [`f(x) = ${problem}`, ''], placeholders: ['', "f'(x) = …"], title: 'Practice problem' }
  if (kind === 'integrate') return { lines: [`∫ (${problem}) dx`, ''], placeholders: ['', '= …'], title: 'Practice problem' }
  return { lines: [problem, ''], placeholders: ['', 'Your next step'], title: 'Practice problem' }
}

export default function TypeWork() {
  const [params] = useSearchParams()
  const init = useMemo(() => starter(params.get('problem'), params.get('kind')), [params])
  const [lines, setLines] = useState<string[]>(init.lines)
  const [errors, setErrors] = useState<Record<number, string>>({})
  const [prepError, setPrepError] = useState<string | null>(null)
  const { state } = useStore()
  const { run, checking, error } = useRunCheck()
  const left = checksLeftToday(state)

  const setLine = (i: number, v: string) => {
    setLines((ls) => ls.map((l, j) => (j === i ? v : l)))
    setErrors((e) => {
      const { [i]: _drop, ...rest } = e
      return rest
    })
  }

  const check = async () => {
    setPrepError(null)
    const filled = lines.map((l) => l.trim()).filter(Boolean)
    if (!filled.length) {
      setPrepError('Type at least one line of work.')
      return
    }
    let parsed
    try {
      parsed = await parseLines(filled)
    } catch (err) {
      setPrepError(err instanceof Error ? err.message : 'Could not reach the server.')
      return
    }
    const errs: Record<number, string> = {}
    let k = 0
    lines.forEach((l, i) => {
      if (!l.trim()) return
      const p = parsed[k++]
      if (p.error) errs[i] = p.error
    })
    setErrors(errs)
    if (Object.keys(errs).length) {
      setPrepError('Some lines can’t be read as math yet — see the red notes.')
      return
    }
    const drafts = filled.map((m, i) => ({ ...blankDraft(i, m), latex: parsed[i].latex ?? '' }))
    const session = newSession({ source: params.get('problem') ? 'practice' : 'typed', title: init.title, drafts })
    await run(session, { isNew: true })
  }

  return (
    <div className="pb-8">
      <PageHeader back title="Type your work" subtitle="One step per line, exactly as you wrote it — mistakes included." />
      <ol className="space-y-4">
        {lines.map((l, i) => (
          <li key={i} className="flex gap-3">
            <span className="mt-3 w-5 shrink-0 text-right text-sm font-semibold text-faint">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <MathInput
                label={`Line ${i + 1}`}
                value={l}
                onChange={(v) => setLine(i, v)}
                placeholder={init.placeholders[i] || 'Next step'}
                autoFocus={i === (init.lines[0] ? 1 : 0)}
                onSubmit={() => {
                  if (i === lines.length - 1) setLines((ls) => [...ls, ''])
                  setTimeout(() => document.querySelectorAll<HTMLInputElement>('input[aria-label^="Line "]')[i + 1]?.focus(), 0)
                }}
              />
              {errors[i] && <p className="mt-1 text-sm text-pen">{errors[i]}</p>}
            </div>
            {lines.length > 1 && (
              <button onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))} className="mt-1.5 grid size-9 shrink-0 place-items-center rounded-full text-faint hover:bg-surface-2 hover:text-ink" aria-label={`Remove line ${i + 1}`}>
                <X className="size-4" />
              </button>
            )}
          </li>
        ))}
      </ol>
      <button onClick={() => setLines((ls) => [...ls, ''])} disabled={lines.length >= 40} className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-line py-3 text-sm font-medium text-muted hover:text-ink">
        <Plus className="size-4" /> Add a line
      </button>

      <details className="mt-5 rounded-2xl bg-surface-2/60 px-4 py-3 text-sm text-muted">
        <summary className="cursor-pointer font-medium text-ink">How to type math</summary>
        <ul className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
          {SYNTAX_TIPS.map(([code, what]) => (
            <li key={code}><code className="rounded bg-surface px-1.5 py-0.5 font-mono text-ink">{code}</code> {what}</li>
          ))}
        </ul>
      </details>

      <div className="mt-6 space-y-2">
        {(prepError || error) && <ErrorNote>{prepError || error} {left <= 0 && <Link to="/plans" className="font-semibold underline">See Plus</Link>}</ErrorNote>}
        <Button size="lg" className="w-full" onClick={check} loading={checking} data-testid="type-check">Check my work</Button>
      </div>
    </div>
  )
}
