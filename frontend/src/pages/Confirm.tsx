import { AlertTriangle, Check, CheckCircle2, ChevronDown, ChevronUp, Combine, Pencil, Plus, StickyNote, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { MathInput, parseLines, SYNTAX_TIPS } from '../components/MathInput'
import { PhotoView } from '../components/PhotoView'
import { Tex } from '../components/Tex'
import { Badge, Button, EmptyState, ErrorNote, LinkButton, PageHeader } from '../components/ui'
import { draftsNeedingAttention, linesOf } from '../lib/checking'
import { blankDraft, problemsOf, useFlow } from '../lib/flow'
import { checksLeftToday } from '../lib/profile'
import { useStore } from '../lib/store'
import type { DraftLine } from '../lib/types'
import { useRunCheck } from '../lib/useRunCheck'

export default function Confirm() {
  const { session, update } = useFlow()
  const { state } = useStore()
  const [editing, setEditing] = useState<string | null>(null)
  const [draftText, setDraftText] = useState('')
  const { run, checking, error } = useRunCheck()
  const [showPhoto, setShowPhoto] = useState(true)
  const [alternativeLatex, setAlternativeLatex] = useState<Record<string, string>>({})

  const drafts = session?.drafts ?? []

  // Render every line (and every alternative reading) with the checker's own parser.
  useEffect(() => {
    if (!session) return
    const texts = session.drafts.map((d) => d.math)
    const alts = [...new Set(session.drafts.flatMap((d) => d.alternatives))]
    parseLines([...texts, ...alts]).then((parsed) => {
      const altMap: Record<string, string> = {}
      alts.forEach((a, i) => {
        const p = parsed[texts.length + i]
        if (p?.latex) altMap[a] = p.latex
      })
      setAlternativeLatex(altMap)
      update((s) => ({
        ...s,
        drafts: s.drafts.map((d) => {
          const i = texts.indexOf(d.math)
          if (i < 0 || d.type === 'note') return d
          const p = parsed[i]
          return { ...d, latex: p.latex ?? d.latex, error: d.math.trim() ? p.error : null, confirmed: d.confirmed && !p.error }
        }),
      }))
    }).catch(() => {})
    // Only on first load of this session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id])

  const attention = useMemo(() => draftsNeedingAttention(drafts), [drafts])
  const left = checksLeftToday(state)

  if (!session) {
    return (
      <EmptyState icon={<StickyNote className="size-6" />} title="Nothing to confirm" action={<LinkButton to="/">Start a check</LinkButton>}>
        Snap, upload or type some work first.
      </EmptyState>
    )
  }

  const patch = (key: string, p: Partial<DraftLine>) =>
    update((s) => ({ ...s, drafts: s.drafts.map((d) => (d.key === key ? { ...d, ...p } : d)), results: {}, checkedLines: {} }))

  const setMath = async (key: string, math: string) => {
    patch(key, { math, confirmed: !!math.trim(), confidence: 'high' })
    if (!math.trim()) return
    try {
      const [p] = await parseLines([math])
      patch(key, { latex: p.latex ?? '', error: p.error, confirmed: !p.error })
    } catch {
      /* preview failed; the check will report it */
    }
  }

  const startEdit = (d: DraftLine) => {
    setEditing(d.key)
    setDraftText(d.math)
  }
  const saveEdit = async () => {
    if (!editing) return
    const key = editing
    setEditing(null)
    await setMath(key, draftText.trim())
  }

  const remove = (key: string) => update((s) => ({ ...s, drafts: s.drafts.filter((d) => d.key !== key), results: {} }))

  const mergeUp = (key: string) => {
    const i = drafts.findIndex((d) => d.key === key)
    if (i <= 0) return
    const prev = drafts[i - 1]
    const cur = drafts[i]
    if (prev.problem !== cur.problem) return
    const box: [number, number, number, number] | undefined = prev.box && cur.box
      ? [Math.min(prev.box[0], cur.box[0]), Math.min(prev.box[1], cur.box[1]), Math.max(prev.box[2], cur.box[2]), Math.max(prev.box[3], cur.box[3])]
      : prev.box ?? cur.box
    const merged: DraftLine = {
      ...prev, math: `${prev.math} ${cur.math}`.trim(), confirmed: false, alternatives: [], box,
      quad: box ? [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]] : undefined,
    }
    update((s) => ({ ...s, drafts: s.drafts.flatMap((d) => (d.key === prev.key ? [merged] : d.key === cur.key ? [] : [d])), results: {} }))
    setEditing(merged.key)
    setDraftText(merged.math)
  }

  const addLine = (problem: number) => {
    const maxIndex = drafts.reduce((m, d) => Math.max(m, d.index), -1)
    const d = blankDraft(maxIndex + 1, '', problem)
    update((s) => {
      const lastPos = s.drafts.map((x) => x.problem).lastIndexOf(problem)
      const next = [...s.drafts]
      next.splice(lastPos + 1, 0, d)
      return { ...s, drafts: next, results: {} }
    })
    setEditing(d.key)
    setDraftText('')
  }

  const runCheck = () => run(session)

  const problems = problemsOf(drafts)
  const marks = drafts.map((d) => ({
    key: d.key,
    quad: d.quad,
    box: d.box,
    label: String((linesOf(drafts, d.problem).indexOf(d)) + 1),
    status: (editing === d.key ? 'selected' : attention.includes(d) ? 'pending' : undefined) as 'selected' | 'pending' | undefined,
  }))

  return (
    <div className="pb-24">
      <PageHeader
        back="/"
        title="Check the reading"
        subtitle={session.readSource === 'manual' ? 'Type what each line says — we found the lines for you.' : 'Make sure each line matches what you wrote.'}
      />

      {session.readSource === 'manual' && (
        <div className="mb-4 rounded-2xl border border-line bg-surface px-4 py-3 text-sm text-muted">
          Handwriting reading isn't set up on this server, so tap each line and type it. The photo crop shows what you wrote.
        </div>
      )}

      {session.photo && (
        <div className="mb-5">
          <button onClick={() => setShowPhoto((v) => !v)} className="mb-2 flex items-center gap-1 text-sm font-medium text-muted">
            {showPhoto ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />} {showPhoto ? 'Hide photo' : 'Show photo'}
          </button>
          {showPhoto && (
            <PhotoView src={session.photo.src} width={session.photo.width} height={session.photo.height} marks={marks} />
          )}
        </div>
      )}

      {problems.map((p) => {
        const lines = linesOf(drafts, p)
        return (
          <section key={p} className="mb-6">
            {session.mode === 'page' && <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">Problem {p + 1}</h2>}
            <ol className="space-y-3">
              {lines.map((d, i) => {
                const needs = attention.includes(d)
                const isEditing = editing === d.key
                return (
                  <li key={d.key} className={`rounded-3xl border bg-surface p-4 transition ${needs ? 'border-warn/60 bg-warn-soft/40' : 'border-line'}`} data-testid="confirm-line">
                    <div className="flex items-start gap-3">
                      <span className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold ${needs ? 'bg-warn text-white' : 'bg-surface-2 text-muted'}`}>{i + 1}</span>
                      <div className="min-w-0 flex-1">
                        {d.crop && <img src={d.crop} alt={`Line ${i + 1} as written`} className="mb-2 max-h-16 max-w-full rounded-lg border border-line bg-white object-contain" />}
                        {isEditing ? (
                          <div className="space-y-2">
                            <MathInput label={`Line ${i + 1}`} value={draftText} onChange={setDraftText} onSubmit={saveEdit} autoFocus />
                            <div className="flex gap-2">
                              <Button size="sm" onClick={saveEdit}><Check className="size-4" /> Done</Button>
                              <Button size="sm" variant="ghost" onClick={() => { setEditing(null); if (!d.math) remove(d.key) }}>Cancel</Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            {d.type === 'note' ? (
                              <p className="text-[15px] italic text-muted">{d.math || 'Note'}</p>
                            ) : d.math ? (
                              <div className="math-scroll py-1 text-[17px]">{d.latex ? <Tex latex={d.latex} /> : <span className="font-mono text-sm">{d.math}</span>}</div>
                            ) : (
                              <button onClick={() => startEdit(d)} className="text-[15px] font-medium text-accent">Type what this line says</button>
                            )}
                            {d.error && d.type !== 'note' && <p className="mt-1 text-sm text-pen">{d.error}</p>}
                          </>
                        )}

                        {!isEditing && d.type !== 'note' && d.alternatives.length > 1 && !d.confirmed && (
                          <div className="mt-3">
                            <p className="mb-2 text-sm font-medium">
                              {d.lookalike ? `Is that a “${d.lookalike.letter}” or a ${d.lookalike.digit}?` : 'Which did you write?'}
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {d.alternatives.map((alt) => (
                                <button key={alt} onClick={() => setMath(d.key, alt)} className="rounded-2xl border border-line bg-surface px-3 py-2 text-[16px] transition hover:border-ink active:scale-[0.98]">
                                  {alternativeLatex[alt] ? <Tex latex={alternativeLatex[alt]} /> : <span className="font-mono text-sm">{alt}</span>}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {!isEditing && (
                          <div className="mt-3 flex flex-wrap items-center gap-1">
                            {d.confirmed && !d.error && d.math ? (
                              <Badge tone="ok"><CheckCircle2 className="size-3.5" /> {d.confidence === 'high' && d.math === d.original ? 'Read confidently' : 'Confirmed'}</Badge>
                            ) : d.math && !d.error && d.type !== 'note' && d.alternatives.length <= 1 ? (
                              <Button size="sm" variant="secondary" onClick={() => patch(d.key, { confirmed: true })}><Check className="size-4" /> Yes, that's right</Button>
                            ) : needs ? (
                              <Badge tone="warn"><AlertTriangle className="size-3.5" /> Please check</Badge>
                            ) : null}
                            <span className="flex-1" />
                            <IconBtn label="Edit" onClick={() => startEdit(d)}><Pencil className="size-4" /></IconBtn>
                            <IconBtn label={d.type === 'note' ? 'Treat as math' : 'Mark as a note (skipped)'} onClick={() => patch(d.key, { type: d.type === 'note' ? 'equation' : 'note', confirmed: true })}>
                              <StickyNote className={`size-4 ${d.type === 'note' ? 'text-accent' : ''}`} />
                            </IconBtn>
                            {i > 0 && <IconBtn label="Join with the line above" onClick={() => mergeUp(d.key)}><Combine className="size-4" /></IconBtn>}
                            <IconBtn label="Delete line" onClick={() => remove(d.key)}><Trash2 className="size-4" /></IconBtn>
                          </div>
                        )}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ol>
            <button onClick={() => addLine(p)} className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-line py-3 text-sm font-medium text-muted hover:text-ink">
              <Plus className="size-4" /> Add a line
            </button>
          </section>
        )
      })}

      <details className="mb-4 rounded-2xl bg-surface-2/60 px-4 py-3 text-sm text-muted">
        <summary className="cursor-pointer font-medium text-ink">How to type math</summary>
        <ul className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
          {SYNTAX_TIPS.map(([code, what]) => (
            <li key={code}><code className="rounded bg-surface px-1.5 py-0.5 font-mono text-ink">{code}</code> {what}</li>
          ))}
        </ul>
      </details>

      <div className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-20 border-t border-line/70 bg-paper/90 px-4 py-3 backdrop-blur-md">
        <div className="mx-auto max-w-2xl space-y-2">
          {error && <ErrorNote>{error} {left <= 0 && <Link to="/plans" className="font-semibold underline">See Plus</Link>}</ErrorNote>}
          <Button size="lg" className="w-full" onClick={runCheck} loading={checking} disabled={!drafts.length} data-testid="check-button">
            {attention.length ? `${attention.length} line${attention.length === 1 ? '' : 's'} need${attention.length === 1 ? 's' : ''} a look` : 'Check my work'}
          </Button>
        </div>
      </div>
    </div>
  )
}

function IconBtn({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-label={label} title={label} className="grid size-8 place-items-center rounded-full text-muted transition hover:bg-surface-2 hover:text-ink">
      {children}
    </button>
  )
}
