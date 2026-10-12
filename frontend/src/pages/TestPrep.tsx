import { Play, Timer, Trophy } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { ProblemCard } from '../components/ProblemCard'
import { Button, Card, ErrorNote, LockCard, PageHeader, Segmented, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { ERROR_LABELS, errorLabel, hasFeature, topMistakes, UNITS } from '../lib/profile'
import { useStore } from '../lib/store'
import type { PracticeProblem } from '../lib/types'
import { SKILL_TITLES } from './Practice'

const DRILL_SECONDS = 600
const FALLBACK: Record<string, string[]> = {
  algebra: ['sign_error', 'distribution_error', 'arithmetic_slip'],
  calculus: ['derivative_rule', 'antiderivative_error', 'limit'],
  all: ['sign_error', 'distribution_error', 'derivative_rule'],
}

export default function TestPrep() {
  const { state, dispatch } = useStore()
  const [unit, setUnit] = useState('algebra')
  const [problems, setProblems] = useState<PracticeProblem[] | null>(null)
  const [results, setResults] = useState<Record<string, boolean>>({})
  const [secondsLeft, setSecondsLeft] = useState(DRILL_SECONDS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const plus = hasFeature(state.plan, 'test_prep')

  const topics = UNITS.find((u) => u.id === unit)?.topics ?? []
  const top = useMemo(() => topMistakes(state.history, topics, 3), [state.history, topics])
  const skills = useMemo(() => {
    const fromHistory = top.map((r) => ERROR_LABELS[r.key]?.skill ?? 'general')
    const fill = FALLBACK[unit].filter((s) => !fromHistory.includes(s))
    return [...fromHistory, ...fill].slice(0, 3)
  }, [top, unit])

  const running = problems !== null
  const answered = Object.keys(results).length
  const finished = running && (secondsLeft <= 0 || answered >= (problems?.length ?? 0))

  useEffect(() => {
    if (!running || finished) return
    const t = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [running, finished])

  const start = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await api.drill(skills, 8, 2)
      setProblems(r.problems)
      setResults({})
      setSecondsLeft(DRILL_SECONDS)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not build the drill')
    } finally {
      setLoading(false)
    }
  }

  if (!plus) {
    return (
      <div>
        <PageHeader back="/practice" title="Test prep" subtitle="Get ready for your next exam" />
        <LockCard title="Test prep is part of Plus">Before an exam, see your top 3 mistake types in the unit and take a 10-minute drill built around them.</LockCard>
      </div>
    )
  }

  const mm = String(Math.floor(secondsLeft / 60)).padStart(1, '0')
  const ss = String(secondsLeft % 60).padStart(2, '0')
  const correct = Object.values(results).filter(Boolean).length

  return (
    <div className="space-y-5">
      <PageHeader back="/practice" title="Test prep" subtitle="Your top mistakes in a unit, then a 10-minute drill" />
      {error && <ErrorNote>{error}</ErrorNote>}

      {!running && (
        <>
          <Segmented label="Unit" value={unit} onChange={setUnit} options={UNITS.map((u) => ({ value: u.id, label: u.label }))} />
          <Card className="p-5">
            <h2 className="font-semibold">Your top 3 to watch</h2>
            <ol className="mt-3 space-y-3">
              {skills.map((s, i) => {
                const row = top.find((r) => (ERROR_LABELS[r.key]?.skill ?? 'general') === s)
                return (
                  <li key={s} className="flex items-center gap-3">
                    <span className="grid size-7 place-items-center rounded-full bg-pen-soft text-sm font-bold text-pen">{i + 1}</span>
                    <div className="flex-1">
                      <p className="font-medium">{SKILL_TITLES[s] ?? s}</p>
                      <p className="text-xs text-muted">{row ? `${row.count} ${errorLabel(row.key, row.count !== 1)} recently (${row.pct}%)` : 'Common in this unit'}</p>
                    </div>
                  </li>
                )
              })}
            </ol>
            <Button size="lg" className="mt-5 w-full" onClick={start} loading={loading}><Play className="size-5" /> Start the 10-minute drill</Button>
          </Card>
        </>
      )}

      {running && (
        <div className="sticky top-16 z-10 flex items-center justify-between rounded-2xl border border-line bg-surface/95 px-4 py-3 backdrop-blur">
          <span className="flex items-center gap-2 font-semibold tabular-nums"><Timer className="size-4" /> {mm}:{ss}</span>
          <span className="text-sm text-muted">{answered} / {problems!.length} answered · {correct} right</span>
        </div>
      )}

      {finished && (
        <Card className="fade-up p-5 text-center">
          <Trophy className="mx-auto size-8 text-warn" />
          <p className="mt-2 text-2xl font-semibold">{correct} of {problems!.length} right</p>
          <p className="mt-1 text-sm text-muted">{secondsLeft <= 0 ? 'Time’s up! ' : ''}Results count toward your practice schedule.</p>
          <div className="mt-4 flex justify-center gap-2">
            <Button onClick={start} loading={loading}>New drill</Button>
            <Button variant="secondary" onClick={() => setProblems(null)}>Back</Button>
          </div>
        </Card>
      )}

      {loading && !running && <Spinner />}
      {running && problems!.map((p, i) => (
        <ProblemCard key={p.id} problem={p} number={i + 1} compact allowReveal={finished} onResult={(c) => {
          setResults((r) => ({ ...r, [p.id]: c }))
          dispatch({ type: 'recordPractice', skill: p.skill, correct: c })
        }} />
      ))}
    </div>
  )
}
