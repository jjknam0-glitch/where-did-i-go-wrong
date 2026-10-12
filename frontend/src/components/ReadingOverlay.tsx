import { Check, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Stage } from '../lib/useCheckStarter'

const STEPS = ['Straightening the page', 'Evening out the lighting', 'Finding each line of work', 'Reading your handwriting']

/** Shown while a photo is uploaded and read. */
export function ReadingOverlay({ stage }: { stage: Stage }) {
  const [step, setStep] = useState(0)
  useEffect(() => {
    if (stage === 'idle') {
      setStep(0)
      return
    }
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 900)
    return () => clearInterval(t)
  }, [stage])
  if (stage === 'idle') return null
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-paper/80 p-6 backdrop-blur-sm" role="status" aria-live="polite">
      <div className="fade-up w-full max-w-xs rounded-3xl border border-line bg-surface p-6 shadow-xl">
        <p className="mb-4 font-semibold">{stage === 'preparing' ? 'Preparing your photo…' : 'Reading your work…'}</p>
        <ol className="space-y-3">
          {STEPS.map((s, i) => (
            <li key={s} className={`flex items-center gap-3 text-sm ${i <= step ? 'text-ink' : 'text-faint'}`}>
              {i < step ? (
                <Check className="size-4 text-ok" aria-hidden />
              ) : i === step ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <span className="size-4 rounded-full border border-line" aria-hidden />
              )}
              {s}
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
