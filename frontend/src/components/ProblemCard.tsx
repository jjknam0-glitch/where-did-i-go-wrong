import { CheckCircle2, Eye, PencilLine, XCircle } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import type { PracticeCheck, PracticeProblem } from '../lib/types'
import { MathInput } from './MathInput'
import { Tex } from './Tex'
import { Button, Card } from './ui'

/** One practice problem: answer it, check it with the engine, or work it out step by step. */
export function ProblemCard({ problem, number, onResult, allowReveal = true, compact = false }: {
  problem: PracticeProblem
  number?: number
  onResult?: (correct: boolean) => void
  allowReveal?: boolean
  compact?: boolean
}) {
  const navigate = useNavigate()
  const [answer, setAnswer] = useState('')
  const [result, setResult] = useState<PracticeCheck | null>(null)
  const [busy, setBusy] = useState(false)
  const [revealed, setRevealed] = useState<string | null>(null)
  const [reported, setReported] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const check = async () => {
    if (!answer.trim()) return
    setBusy(true)
    setError(null)
    try {
      const r = await api.practiceCheck(problem, answer)
      setResult(r)
      if (!reported && (r.correct || !r.equivalent)) {
        setReported(true)
        onResult?.(r.correct)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Check failed')
    } finally {
      setBusy(false)
    }
  }

  const reveal = async () => {
    try {
      const a = await api.practiceAnswer(problem)
      setRevealed(a.available && a.latex ? a.latex : 'Not available')
      if (!reported) {
        setReported(true)
        onResult?.(false)
      }
    } catch {
      setRevealed('Not available')
    }
  }

  const placeholder = problem.kind === 'solve' ? 'x = …' : problem.kind === 'solve_system' ? 'x = …, y = …' : 'Your answer'

  return (
    <Card className={compact ? 'p-4' : 'p-5'} data-testid="problem-card">
      <div className="mb-1 flex items-center gap-2 text-xs font-medium text-muted">
        {number !== undefined && <span className="rounded-full bg-surface-2 px-2 py-0.5">#{number}</span>}
        <span>{problem.prompt.replace(/\$x\$/g, 'x')}</span>
      </div>
      <div className="math-scroll py-2 text-xl"><Tex latex={problem.latex} display /></div>
      {result?.correct ? (
        <div className="mt-2 flex items-center gap-2 rounded-2xl bg-ok-soft px-4 py-3 text-ok">
          <CheckCircle2 className="size-5" /> <span className="font-medium">{result.message}</span>
        </div>
      ) : (
        <div className="mt-2 space-y-3">
          <MathInput label="Your answer" value={answer} onChange={setAnswer} onSubmit={check} placeholder={placeholder} />
          {result && !result.correct && (
            <div className="flex items-start gap-2 rounded-2xl bg-pen-soft px-4 py-3 text-sm text-pen" role="status">
              <XCircle className="mt-0.5 size-4 shrink-0" /> {result.message}
            </div>
          )}
          {error && <p className="text-sm text-pen">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <Button onClick={check} loading={busy} disabled={!answer.trim()}>Check answer</Button>
            <Button variant="secondary" onClick={() => navigate(`/type?problem=${encodeURIComponent(problem.math)}&kind=${problem.kind}`)}>
              <PencilLine className="size-4" /> Work it out
            </Button>
            {allowReveal && !revealed && (
              <Button variant="ghost" onClick={reveal}><Eye className="size-4" /> Show answer</Button>
            )}
          </div>
        </div>
      )}
      {revealed && (
        <p className="mt-3 rounded-2xl bg-surface-2 px-4 py-3 text-sm">
          Answer (verified by the engine): {revealed === 'Not available' ? revealed : <Tex latex={revealed} />}
        </p>
      )}
    </Card>
  )
}
