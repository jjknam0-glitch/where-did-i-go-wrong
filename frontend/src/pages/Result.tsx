import { BookOpen, Camera, CheckCircle2, ChevronRight, Dumbbell, Eye, ImageDown, Lightbulb, Lock, Pencil, RotateCcw, Share2, Sparkles, Wrench } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FixSheet } from '../components/FixSheet'
import { parseLines } from '../components/MathInput'
import { PhotoView, type PhotoMark } from '../components/PhotoView'
import { ProblemCard } from '../components/ProblemCard'
import { STATUS_TEXT, StatusIcon, TierBadge, TierLegend } from '../components/StatusBits'
import { Tex, TexText } from '../components/Tex'
import { Badge, Button, Card, EmptyState, ErrorNote, LinkButton, LockCard, PageHeader, Segmented, Sheet, Toggle, useToast } from '../components/ui'
import { api } from '../lib/api'
import { buildHistoryEntry, historyId, linesOf, payloadFor } from '../lib/checking'
import { problemsOf, useFlow } from '../lib/flow'
import { dataUrlToBlob } from '../lib/image'
import { deletePhoto, savePhoto } from '../lib/photos'
import { ERROR_LABELS, errorLabel, fixStreak, hasFeature, patternMessage, topicLabel } from '../lib/profile'
import { useStore } from '../lib/store'
import type { CheckResponse, DraftLine, FixResponse, PracticeProblem } from '../lib/types'
import { useHealth } from '../lib/useHealth'
import { makeWinCard, shareOrDownload } from '../lib/winCard'

export default function Result() {
  const { session, update, clear, photoBlob } = useFlow()
  const { state, dispatch } = useStore()
  const { health } = useHealth()
  const toast = useToast()
  const navigate = useNavigate()
  const problems = session ? problemsOf(session.drafts).filter((p) => session.results[p]) : []
  const [problem, setProblem] = useState<number>(problems[0] ?? 0)
  const [fixOpen, setFixOpen] = useState(false)
  const [answerOpen, setAnswerOpen] = useState(false)
  const [answer, setAnswer] = useState<string | null>(null)
  const [answerBusy, setAnswerBusy] = useState(false)
  const [recheckBusy, setRecheckBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aiHints, setAiHints] = useState<Record<string, string[]>>({})
  const [harder, setHarder] = useState<PracticeProblem | null>(null)
  const [harderBusy, setHarderBusy] = useState(false)
  const [justFixed, setJustFixed] = useState(false)
  const [legendOpen, setLegendOpen] = useState(false)

  const result: CheckResponse | undefined = session?.results[problem]
  const lines: DraftLine[] = session ? session.checkedLines[problem] ?? linesOf(session.drafts, problem) : []
  const locked = !!result?.advanced && !hasFeature(state.plan, 'advanced')
  const firstError = result?.first_error ?? null
  const errorLine = result && firstError !== null ? result.lines.find((l) => l.index === firstError) : undefined
  const hintsShown = session?.hintsShown[problem] ?? 1
  const allHints = hasFeature(state.plan, 'all_hints')
  const entryId = session ? historyId(session, problem) : ''
  const entry = state.history.find((h) => h.id === entryId)
  const conflict = result?.sanity_check === 'conflict'
  const aiKey = `${problem}:${firstError}:${lines[firstError ?? 0]?.math ?? ''}`

  // Ask the AI to phrase hints 2 and 3 (verified by the engine) while hint 1 is showing.
  const askedRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    if (!health?.ai_hints || !errorLine?.hints || locked || firstError === null) return
    if (askedRef.current.has(aiKey)) return
    askedRef.current.add(aiKey)
    const prevIdx = errorLine.compared_to ?? Math.max(0, firstError - 1)
    api.explain({
      previous: lines[prevIdx]?.math ?? '',
      student: lines[firstError]?.math ?? '',
      corrected: errorLine.corrected,
      error_type: errorLine.error_type,
      hints: errorLine.hints,
      variable: result?.variable,
    }).then((r) => {
      if (r.source === 'ai') setAiHints((h) => ({ ...h, [aiKey]: r.hints }))
    }).catch(() => {})
  }, [aiKey, errorLine, firstError, health?.ai_hints, lines, locked, result?.variable])

  const hints = useMemo(() => {
    const base = errorLine?.hints ?? []
    const ai = aiHints[aiKey]
    // Never swap the text of a hint the student has already read.
    if (ai && hintsShown <= 1) return [base[0], ai[1], ai[2]]
    return base
  }, [aiHints, aiKey, errorLine, hintsShown])

  if (!session || !result) {
    return (
      <EmptyState icon={<Sparkles className="size-6" />} title="No result yet" action={session?.drafts.length ? <LinkButton to="/confirm">Back to your lines</LinkButton> : <LinkButton to="/">Start a check</LinkButton>}>
        Check some work and the result will show up here.
      </EmptyState>
    )
  }

  const statusOf = (i: number) => result.lines.find((l) => l.index === i)
  const marks: PhotoMark[] = session.drafts
    .filter((d) => d.problem === problem)
    .map((d, i) => {
      const st = locked ? undefined : statusOf(i)?.status
      // A line the student rewrote no longer matches the photo: mark it as fixed, not as their original.
      const fixedLine = (session.editedKeys ?? []).includes(d.key) && (st === 'ok' || st === 'start')
      return { key: d.key, quad: d.quad, box: d.box, status: fixedLine ? 'fixed' as const : st }
    })
    .filter((m) => m.status !== 'error')
  const errorDraft = firstError !== null ? session.drafts.filter((d) => d.problem === problem)[firstError] : undefined
  const circle = !locked && errorDraft && (errorDraft.quad || errorDraft.box) ? { key: 'err', quad: errorDraft.quad, box: errorDraft.box } : null

  const showHint = (n: number) => {
    update((s) => ({ ...s, hintsShown: { ...s.hintsShown, [problem]: Math.max(n, s.hintsShown[problem] ?? 1) } }))
    if (entry) dispatch({ type: 'updateHistory', id: entry.id, patch: { hintsUsed: Math.max(entry.hintsUsed, n) } })
  }

  const onFixed = async (res: FixResponse, math: string) => {
    setFixOpen(false)
    if (!res.check || firstError === null) return
    const [parsed] = await parseLines([math]).catch(() => [{ latex: null, error: null }])
    const target = lines[firstError]
    const newLines = lines.map((l, i) => (i === firstError ? { ...l, math, latex: parsed?.latex ?? l.latex, confirmed: true, error: null } : l))
    update((s) => ({
      ...s,
      drafts: s.drafts.map((d) => (d.key === target.key ? { ...d, math, latex: parsed?.latex ?? d.latex, confirmed: true, error: null } : d)),
      checkedLines: { ...s.checkedLines, [problem]: newLines },
      results: { ...s.results, [problem]: res.check! },
      hintsShown: { ...s.hintsShown, [problem]: 1 },
      fixed: { ...s.fixed, [problem]: true },
      editedKeys: [...(s.editedKeys ?? []), target.key],
    }))
    if (!locked) {
      const prev = state.history.find((h) => h.id === entryId)
      const next = buildHistoryEntry(session, problem, res.check, newLines, prev)
      next.fixed = true
      next.fixedAt = prev?.fixedAt ?? Date.now()
      dispatch({ type: 'addHistory', entry: next, countsAsCheck: false })
    }
    setJustFixed(true)
    toast(res.check.all_correct ? 'You fixed it — every step checks out!' : 'That step is right now. On to the next one.', 'ok')
  }

  const recheckAcknowledged = async () => {
    setRecheckBusy(true)
    setError(null)
    try {
      const r = await api.check(payloadFor(lines), true)
      update((s) => ({ ...s, results: { ...s.results, [problem]: r } }))
      if (!locked) {
        const prev = state.history.find((h) => h.id === entryId)
        dispatch({ type: 'addHistory', entry: buildHistoryEntry(session, problem, r, lines, prev ? { ...prev, errors: [] } : undefined), countsAsCheck: false })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Re-check failed')
    } finally {
      setRecheckBusy(false)
    }
  }

  const loadAnswer = async () => {
    setAnswerBusy(true)
    try {
      const a = await api.answer(payloadFor(lines))
      setAnswer(a.available && a.latex ? a.latex : a.message ?? 'Not available for this problem.')
    } catch (err) {
      setAnswer(err instanceof Error ? err.message : 'Not available')
    } finally {
      setAnswerBusy(false)
    }
  }

  const loadHarder = async () => {
    setHarderBusy(true)
    try {
      const r = await api.harder(result.topic, 2)
      setHarder(r.problems[0] ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load a problem')
    } finally {
      setHarderBusy(false)
    }
  }

  const togglePhoto = async (on: boolean) => {
    update((s) => ({ ...s, savePhoto: on }))
    if (!entry || session.source !== 'photo') return
    if (on) {
      const blob = photoBlob ?? (session.photo?.src.startsWith('data:') ? await dataUrlToBlob(session.photo.src) : null)
      if (blob && (await savePhoto(session.id, blob))) {
        for (const p of problems) dispatch({ type: 'updateHistory', id: historyId(session, p), patch: { photoId: session.id } })
        toast('Photo saved to your history (on this device only)')
      } else toast("Couldn't save the photo on this device", 'pen')
    } else {
      await deletePhoto(session.id)
      for (const p of problems) dispatch({ type: 'updateHistory', id: historyId(session, p), patch: { photoId: undefined } })
    }
  }

  const shareWin = async () => {
    const streak = fixStreak(state.history)
    const blob = await makeWinCard({
      headline: 'I fixed my own mistake!',
      detail: streak > 1 ? `${streak} mistakes in a row found and fixed — no answer key needed.` : 'Found the broken step and fixed it myself.',
      topic: topicLabel(result.topic),
    })
    if (!blob) return
    const r = await shareOrDownload(blob, 'i-fixed-my-mistake.png', 'I fixed my own math mistake!')
    if (r === 'downloaded') toast('Card saved — share it anywhere')
  }

  const errorName = errorLine?.error_type ? (ERROR_LABELS[errorLine.error_type] ? errorLabel(errorLine.error_type) : errorLine.error_name) : null
  const uncertainCount = result.lines.filter((l) => l.status === 'uncertain').length
  const warnings = result.lines.filter((l) => l.status === 'warning')

  return (
    <div className="space-y-5 pb-10">
      <PageHeader back="/confirm" title={session.title ?? 'Your result'} subtitle={`${topicLabel(result.topic)}${session.mode === 'page' ? ` · ${problems.length} problems` : ''}`} />

      {problems.length > 1 && (
        <div className="-mx-4 overflow-x-auto px-4">
          <Segmented<string> label="Problem" value={String(problem)} onChange={(v) => setProblem(Number(v))}
            options={problems.map((p) => {
              const r = session.results[p]
              const mark = r.first_error !== null ? ' ✗' : r.all_correct ? ' ✓' : ''
              return { value: String(p), label: `Problem ${p + 1}${mark}` }
            })} />
        </div>
      )}

      {error && <ErrorNote>{error}</ErrorNote>}

      {/* Summary */}
      {locked ? (
        <LockCard title={`${topicLabel(result.topic)} checking is part of Plus`}>
          Calculus is checked by verifying your answers — differentiating antiderivatives, comparing derivatives. Algebra stays free.
        </LockCard>
      ) : conflict ? (
        <Card className="border-warn/50 bg-warn-soft/50 p-5">
          <p className="font-semibold">Your final answer is right, but a step in the middle doesn't follow.</p>
          <p className="mt-1 text-sm text-muted">That usually means we misread a line — or two mistakes cancelled out. Please double-check the highlighted line.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => navigate('/confirm')}><Pencil className="size-4" /> Fix the reading</Button>
            <Button size="sm" onClick={recheckAcknowledged} loading={recheckBusy}>It's read correctly — show me</Button>
          </div>
        </Card>
      ) : firstError !== null ? (
        <Card className="fade-up border-pen/30 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="pen">Line {firstError + 1}</Badge>
            {errorName && <Badge>{errorName}</Badge>}
            {errorLine?.tier && <TierBadge tier={errorLine.tier} status="error" />}
          </div>
          <p className="mt-3 text-xl font-semibold tracking-tight">This is where it went wrong.</p>
          {entry?.errors[0] && !session.fixed[problem] && (
            <p className="mt-1 text-sm text-muted">{patternMessage(state.history, entry.errors[0].type)}</p>
          )}
        </Card>
      ) : result.all_correct ? (
        <Card className="fade-up border-ok/30 bg-ok-soft/40 p-5">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="pop-in size-9 text-ok" />
            <div>
              <p className="text-xl font-semibold tracking-tight">{session.fixed[problem] ? 'Fixed — every step checks out.' : 'Every step checks out.'}</p>
              <p className="text-sm text-muted">Each line was verified by the math engine.</p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {!harder && <Button size="sm" onClick={loadHarder} loading={harderBusy}><Dumbbell className="size-4" /> Try a harder one</Button>}
            {session.fixed[problem] && <Button size="sm" variant="secondary" onClick={shareWin}><Share2 className="size-4" /> Share your win</Button>}
          </div>
        </Card>
      ) : (
        <Card className="p-5">
          <p className="text-lg font-semibold">{uncertainCount ? `We couldn't verify ${uncertainCount === 1 ? 'one step' : `${uncertainCount} steps`}.` : 'No mistakes found.'}</p>
          <p className="mt-1 text-sm text-muted">
            {uncertainCount ? "Rather than guess, we're flagging them. Check that each is read correctly." : warnings.length ? 'Have a look at the yellow flags below.' : ''}
          </p>
          {uncertainCount > 0 && <Button size="sm" variant="secondary" className="mt-3" onClick={() => navigate('/confirm')}><Pencil className="size-4" /> Review the lines</Button>}
        </Card>
      )}

      {harder && <ProblemCard problem={harder} onResult={(c) => dispatch({ type: 'recordPractice', skill: harder.skill, correct: c })} />}

      {session.photo && (
        <PhotoView src={session.photo.src} width={session.photo.width} height={session.photo.height} marks={marks} circle={circle} />
      )}

      {/* Hint ladder */}
      {!locked && !conflict && errorLine && (
        <Card className="p-5" data-testid="hint-ladder">
          <div className="mb-3 flex items-center gap-2">
            <Lightbulb className="size-5 text-warn" />
            <h2 className="font-semibold">Hints</h2>
            <span className="text-xs text-muted">Take as much help as you need</span>
          </div>
          <ol className="space-y-3">
            {[0, 1, 2].map((i) => {
              const label = ['Where', 'What kind', 'The fix'][i]
              const shown = i < hintsShown
              const lockedHint = i > 0 && !allHints
              return (
                <li key={i} className={`rounded-2xl p-4 ${shown ? 'bg-surface-2/70' : 'border border-dashed border-line'}`}>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Hint {i + 1} · {label}</p>
                  {shown && hints[i] ? (
                    <p className="fade-up text-[15px] leading-relaxed" data-testid={`hint-${i + 1}`}><TexText text={hints[i]} /></p>
                  ) : lockedHint ? (
                    <Link to="/plans" className="flex items-center gap-1.5 text-sm font-medium text-accent"><Lock className="size-3.5" /> Hints 2 and 3 come with Plus</Link>
                  ) : i === hintsShown ? (
                    <Button size="sm" variant="secondary" onClick={() => showHint(i + 1)} data-testid={`show-hint-${i + 1}`}>Show hint {i + 1}</Button>
                  ) : (
                    <p className="text-sm text-faint">Unlocks after hint {i}</p>
                  )}
                </li>
              )
            })}
          </ol>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Button size="lg" variant="pen" onClick={() => setFixOpen(true)} data-testid="fix-button"><Wrench className="size-5" /> Fix it yourself</Button>
            {errorLine.lesson && (
              <LinkButton to={`/lessons/${errorLine.lesson}`} variant="secondary" size="lg"><BookOpen className="size-5" /> Why does this rule work?</LinkButton>
            )}
          </div>
        </Card>
      )}

      {/* Practice this */}
      {!locked && errorLine?.error_type && (
        hasFeature(state.plan, 'practice') ? (
          <Link to={`/practice?skill=${ERROR_LABELS[errorLine.error_type]?.skill ?? 'general'}`}>
            <Card className="flex items-center gap-3 p-4 transition hover:shadow-md">
              <div className="grid size-10 place-items-center rounded-2xl bg-accent-soft text-accent"><Dumbbell className="size-5" /></div>
              <div className="flex-1">
                <p className="font-medium">Practice this</p>
                <p className="text-sm text-muted">Three problems aimed at {errorLabel(errorLine.error_type, true)}</p>
              </div>
              <ChevronRight className="size-5 text-faint" />
            </Card>
          </Link>
        ) : (
          <LockCard compact title="Practice this mistake">Three targeted problems with answers verified by the engine — part of Plus.</LockCard>
        )
      )}

      {/* Line by line */}
      {!locked && (
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold">Line by line</h2>
            <button onClick={() => setLegendOpen(true)} className="rounded-full px-2.5 py-1 text-xs font-medium text-muted hover:bg-surface-2">What do the labels mean?</button>
          </div>
          <ol className="space-y-2">
            {lines.map((d, i) => {
              const r = statusOf(i)
              if (!r) return null
              const isErr = r.status === 'error' && i === firstError
              return (
                <li key={d.key} className={`rounded-2xl border p-4 ${isErr ? 'border-pen/50 bg-pen-soft/40' : r.status === 'follows_from_error' ? 'border-line bg-surface opacity-75' : 'border-line bg-surface'}`} data-testid="result-line" data-status={r.status}>
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 w-5 shrink-0 text-right text-sm font-semibold text-faint">{i + 1}</span>
                    <StatusIcon status={r.status} />
                    <div className="min-w-0 flex-1">
                      <div className="math-scroll text-[17px]">
                        {d.type === 'note' ? <span className="italic text-muted">{d.math}</span> : d.latex ? <Tex latex={d.latex} /> : <span className="font-mono text-sm">{d.math}</span>}
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <span className="text-xs text-muted">{r.status === 'error' && !isErr ? 'Another mistake — fix the first one first' : STATUS_TEXT[r.status]}</span>
                        <TierBadge tier={r.tier} status={r.status} />
                      </div>
                      {r.note && <p className="mt-1.5 text-sm text-muted"><TexText text={r.note} /></p>}
                      {r.status === 'uncertain' && r.message && (
                        <p className="mt-1.5 text-sm text-warn">{r.message} <button className="font-medium underline" onClick={() => navigate('/confirm')}>Edit line</button></p>
                      )}
                      {r.status === 'warning' && r.hints && (
                        <div className="mt-2 space-y-1 rounded-xl bg-warn-soft/60 p-3 text-sm">
                          {r.hints.slice(1).map((h, k) => <p key={k}><TexText text={h} /></p>)}
                        </div>
                      )}
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>
        </section>
      )}

      {/* Extras */}
      <Card className="divide-y divide-line px-5">
        {session.source === 'photo' && entry && (
          <Toggle id="save-photo" checked={!!entry.photoId} onChange={togglePhoto} label={<span className="flex items-center gap-2"><ImageDown className="size-4" /> Save the photo to my history</span>}
            description="Kept only on this device. Otherwise photos are discarded after the check." />
        )}
        <button onClick={() => { setAnswerOpen(true); setAnswer(null) }} className="flex w-full items-center gap-2 py-3 text-left text-[15px] font-medium">
          <Eye className="size-4 text-muted" /> Show the final answer
          <ChevronRight className="ml-auto size-4 text-faint" />
        </button>
        {justFixed && session.fixed[problem] && (
          <button onClick={shareWin} className="flex w-full items-center gap-2 py-3 text-left text-[15px] font-medium">
            <Share2 className="size-4 text-muted" /> Share an "I fixed my own mistake" card
            <ChevronRight className="ml-auto size-4 text-faint" />
          </button>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-3">
        <Button variant="secondary" size="lg" onClick={() => navigate('/confirm')}><Pencil className="size-4" /> Edit lines</Button>
        <Button size="lg" onClick={() => { clear(); navigate('/') }}><Camera className="size-4" /> New check</Button>
      </div>

      {firstError !== null && (
        <FixSheet open={fixOpen} onClose={() => setFixOpen(false)} lines={lines} position={firstError} onFixed={onFixed} transcription={!!health?.transcription} />
      )}

      <Sheet open={answerOpen} onClose={() => setAnswerOpen(false)} title="Show the final answer?">
        {answer === null ? (
          <>
            <p className="text-[15px] text-muted">You'll remember more if you find the fix yourself. The hints walk you there one step at a time.</p>
            <div className="mt-5 grid gap-2">
              <Button variant="secondary" onClick={() => setAnswerOpen(false)}>Keep trying</Button>
              <Button onClick={loadAnswer} loading={answerBusy} data-testid="reveal-answer"><RotateCcw className="size-4" /> Yes, show me</Button>
            </div>
          </>
        ) : (
          <div className="rounded-2xl bg-surface-2 p-4 text-center text-lg" data-testid="final-answer">
            {/^[A-Z]/.test(answer) && !answer.includes('\\') ? <p className="text-sm text-muted">{answer}</p> : <Tex latex={answer} display />}
          </div>
        )}
      </Sheet>

      <Sheet open={legendOpen} onClose={() => setLegendOpen(false)} title="How each step was judged">
        <TierLegend />
        <p className="mt-4 text-sm text-muted">The red circle marks the first broken step. Later lines that correctly follow from it are marked “consistent with your earlier step”.</p>
      </Sheet>
    </div>
  )
}
