import { CalendarClock, ChevronRight, Dumbbell, RefreshCw, Target, Timer } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ProblemCard } from '../components/ProblemCard'
import { Button, Card, ErrorNote, LockCard, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { ERROR_LABELS, errorLabel, hasFeature, weakestSkill } from '../lib/profile'
import { useStore } from '../lib/store'
import type { PracticeProblem } from '../lib/types'

export const SKILL_TITLES: Record<string, string> = {
  sign_error: 'Moving terms across the equals sign',
  one_side_only: 'Doing the same thing to both sides',
  distribution_error: 'Distributing, especially negatives',
  arithmetic_slip: 'Careful multi-step arithmetic',
  exponent_rule: 'Exponent rules',
  inequality_flip: 'Inequalities with negatives',
  derivative_rule: 'Derivative rules',
  antiderivative_error: 'Antiderivatives',
  lost_solution: 'Keeping every solution',
  extra_solution: 'Checking for extra solutions',
  general: 'Mixed equations',
  linear: 'Linear equations',
  quadratic: 'Quadratic equations',
  simplify: 'Simplifying expressions',
  factor: 'Factoring',
  derivative: 'Derivatives',
  integral: 'Integrals',
  inequality: 'Inequalities',
  system: 'Systems of equations',
  limit: 'Limits',
  exponential: 'Exponential equations',
}

const MISTAKE_SKILLS = Object.keys(ERROR_LABELS).filter((k) => k !== 'general')
const TOPIC_SKILLS = ['linear', 'quadratic', 'simplify', 'factor', 'inequality', 'system', 'exponential', 'derivative', 'integral', 'limit']

function levelFor(box: number | undefined): number {
  if (!box || box < 2) return 1
  return box < 4 ? 2 : 3
}

function dueText(due: number): string {
  const days = Math.round((due - Date.now()) / 86_400_000)
  if (days <= 0) return 'due now'
  return days === 1 ? 'due tomorrow' : `due in ${days} days`
}

export default function Practice() {
  const { state, dispatch } = useStore()
  const [params, setParams] = useSearchParams()
  const skill = params.get('skill')
  const plus = hasFeature(state.plan, 'practice')
  const [problems, setProblems] = useState<PracticeProblem[] | null>(null)
  const [results, setResults] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const srsRef = useRef(state.srs)
  srsRef.current = state.srs
  const weakest = weakestSkill(state.history)
  const due = useMemo(() => Object.entries(state.srs).filter(([, p]) => p.due <= Date.now()).map(([k]) => k), [state.srs])

  const load = useCallback(async (s: string) => {
    setLoading(true)
    setError(null)
    setResults({})
    try {
      const r = await api.practice(s, 3, levelFor(srsRef.current[s]?.box))
      setProblems(r.problems)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load problems')
      setProblems(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (skill && plus) load(skill)
    else setProblems(null)
  }, [skill, plus, load])

  if (!plus) {
    return (
      <div className="space-y-5">
        <PageHeader title="Practice" subtitle="New problems aimed at your weakest mistake" />
        <LockCard title="Targeted practice is part of Plus">
          Every mistake you make is classified, so Plus can build problems aimed at exactly the kind you make most — with answers
          verified by the math engine and spaced repetition to make it stick.
        </LockCard>
        <Card className="p-5">
          <p className="font-medium">Free for everyone</p>
          <p className="mt-1 text-sm text-muted">Concept mini-lessons explain why each rule works, with a worked example checked by the engine.</p>
          <Link to="/lessons" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-accent">Browse lessons <ChevronRight className="size-4" /></Link>
        </Card>
      </div>
    )
  }

  if (skill) {
    const answered = Object.keys(results).length
    const correct = Object.values(results).filter(Boolean).length
    const done = problems && answered >= problems.length
    const progress = state.srs[skill]
    return (
      <div className="space-y-4">
        <PageHeader back="/practice" title={SKILL_TITLES[skill] ?? 'Practice'} subtitle="Answers are checked by the math engine." />
        {error && <ErrorNote>{error}</ErrorNote>}
        {loading && <Spinner label="Building your problems…" />}
        {!loading && problems?.map((p, i) => (
          <ProblemCard key={p.id} problem={p} number={i + 1} onResult={(c) => {
            setResults((r) => ({ ...r, [p.id]: c }))
            dispatch({ type: 'recordPractice', skill, correct: c })
          }} />
        ))}
        {done && (
          <Card className="fade-up p-5 text-center">
            <p className="text-2xl font-semibold">{correct} of {problems!.length} right</p>
            <p className="mt-1 text-sm text-muted">
              {progress ? `Next review ${dueText(progress.due)}.` : ''} {correct === problems!.length ? 'Nice — the next set will be a little harder.' : 'We’ll bring this back soon.'}
            </p>
            <div className="mt-4 flex justify-center gap-2">
              <Button onClick={() => load(skill)}><RefreshCw className="size-4" /> Three more</Button>
              <Button variant="secondary" onClick={() => setParams({})}>Done</Button>
            </div>
          </Card>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Practice" subtitle="New problems aimed at your weakest mistake" />

      {weakest ? (
        <Card className="p-5">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-muted"><Target className="size-4" /> Recommended for you</div>
          <p className="text-xl font-semibold tracking-tight">{SKILL_TITLES[ERROR_LABELS[weakest]?.skill ?? 'general']}</p>
          <p className="mt-1 text-sm text-muted">Your most common mistake lately is the {errorLabel(weakest)}.</p>
          <Button className="mt-4" onClick={() => setParams({ skill: ERROR_LABELS[weakest]?.skill ?? 'general' })}><Dumbbell className="size-4" /> Practice 3 problems</Button>
        </Card>
      ) : (
        <Card className="p-5">
          <p className="font-medium">Check a few problems first</p>
          <p className="mt-1 text-sm text-muted">Once we've seen your mistakes, we'll recommend exactly what to practice. Meanwhile, pick any skill below.</p>
        </Card>
      )}

      <Link to="/test-prep">
        <Card className="flex items-center gap-3 p-4 transition hover:shadow-md">
          <div className="grid size-10 place-items-center rounded-2xl bg-warn-soft text-warn"><Timer className="size-5" /></div>
          <div className="flex-1">
            <p className="font-medium">Test prep</p>
            <p className="text-sm text-muted">Your top 3 mistake types in a unit, plus a 10-minute drill</p>
          </div>
          <ChevronRight className="size-5 text-faint" />
        </Card>
      </Link>

      {due.length > 0 && (
        <section>
          <h2 className="mb-2 flex items-center gap-2 font-semibold"><CalendarClock className="size-4" /> Due for review</h2>
          <SkillList skills={due} onPick={(s) => setParams({ skill: s })} srs={state.srs} />
        </section>
      )}
      <section>
        <h2 className="mb-2 font-semibold">By kind of mistake</h2>
        <SkillList skills={MISTAKE_SKILLS.map((k) => ERROR_LABELS[k].skill)} onPick={(s) => setParams({ skill: s })} srs={state.srs} />
      </section>
      <section>
        <h2 className="mb-2 font-semibold">By topic</h2>
        <SkillList skills={TOPIC_SKILLS} onPick={(s) => setParams({ skill: s })} srs={state.srs} />
      </section>
    </div>
  )
}

function SkillList({ skills, onPick, srs }: { skills: string[]; onPick: (s: string) => void; srs: Record<string, { due: number; attempts: number; correct: number }> }) {
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-3xl border border-line bg-surface">
      {skills.map((s) => {
        const p = srs[s]
        return (
          <li key={s}>
            <button onClick={() => onPick(s)} className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-surface-2">
              <span className="flex-1">
                <span className="block text-[15px] font-medium">{SKILL_TITLES[s] ?? s}</span>
                {p && <span className="text-xs text-muted">{p.correct}/{p.attempts} right · {dueText(p.due)}</span>}
              </span>
              <ChevronRight className="size-4 text-faint" />
            </button>
          </li>
        )
      })}
    </ul>
  )
}
