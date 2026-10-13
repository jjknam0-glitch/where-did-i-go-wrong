import { Check, Minus } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, PageHeader, useToast } from '../components/ui'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import type { Plan } from '../lib/types'

const ROWS: [string, string, string | boolean, string | boolean][] = [
  ['Guided camera', 'Live coaching and auto-capture', true, true],
  ['Error locator', 'Circles the first broken step', 'A few checks a day', 'Unlimited'],
  ['Hint ladder', 'Where, what kind, the fix', 'Hint 1 only', 'All three hints'],
  ['Fix it yourself', 'Rewrite and re-check the broken step', true, true],
  ['Algebra', 'Equations, simplifying, factoring', true, true],
  ['Advanced math', 'Calculus now; more later', false, true],
  ['Mistake profile', 'Error patterns by type and topic', 'Last 7 days', 'Full history'],
  ['Targeted practice', 'Problems aimed at your weakest mistake, spaced repetition', false, true],
  ['Whole-page mode', 'A report for every problem on a page', false, true],
  ['Test prep', 'Top 3 mistake types plus a 10-minute drill', false, true],
  ['History', 'Every problem checked, searchable', 'Last 7 days', 'Full history'],
  ['Parent & tutor sharing', 'Progress and patterns, not answers', false, true],
  ['Concept mini-lessons', '"Why does this rule work?"', true, true],
  ['Streaks and progress', '"5 problems with no sign errors in a row"', true, true],
]

function Cell({ v }: { v: string | boolean }) {
  if (v === true) return <Check className="mx-auto size-4 text-ok" aria-label="Included" />
  if (v === false) return <Minus className="mx-auto size-4 text-faint" aria-label="Not included" />
  return <span className="text-xs">{v}</span>
}

export default function Plans() {
  const { state, dispatch } = useStore()
  const toast = useToast()
  const [busy, setBusy] = useState<Plan | null>(null)

  const choose = async (plan: Plan) => {
    setBusy(plan)
    try {
      if (state.account) await api.updateMe(state.account.token, { plan }).catch(() => {})
      dispatch({ type: 'setPlan', plan })
      toast(plan === 'free' ? 'Switched to Free' : `${plan === 'family' ? 'Family' : 'Plus'} is on — enjoy everything`, 'ok')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader back="/more" title="Plans" subtitle="Free finds your mistake. Plus helps you stop making it." />

      <div className="rounded-2xl border border-accent/30 bg-accent-soft/60 px-4 py-3 text-sm">
        <span className="font-semibold">Early access:</span> payments aren't switched on yet, so every plan is free to try — no card needed. Pricing will be announced before launch.
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <PlanCard name="Free" blurb="A few checks a day, the red circle, hint 1, algebra." current={state.plan === 'free'} busy={busy === 'free'} onChoose={() => choose('free')} cta="Use Free" />
        <PlanCard name="Plus" blurb="Everything, for one student. Annual discount timed to the school year." current={state.plan === 'plus'} busy={busy === 'plus'} onChoose={() => choose('plus')} cta="Try Plus" highlight />
        <PlanCard name="Family" blurb="Plus for several students, with a single parent view." current={state.plan === 'family'} busy={busy === 'family'} onChoose={() => choose('family')} cta="Try Family" />
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-surface-2/70 text-xs uppercase tracking-wide text-muted">
            <tr><th className="px-4 py-3 font-semibold">Feature</th><th className="w-24 px-2 py-3 text-center font-semibold">Free</th><th className="w-24 px-2 py-3 text-center font-semibold">Plus</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {ROWS.map(([name, desc, free, plus]) => (
              <tr key={name}>
                <td className="px-4 py-3"><p className="font-medium">{name}</p><p className="text-xs text-muted">{desc}</p></td>
                <td className="px-2 py-3 text-center text-muted"><Cell v={free} /></td>
                <td className="px-2 py-3 text-center"><Cell v={plus} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-center text-xs text-muted">The app never shows a final answer unless you ask — on any plan.</p>
    </div>
  )
}

function PlanCard({ name, blurb, current, onChoose, cta, highlight = false, busy }: { name: string; blurb: string; current: boolean; onChoose: () => void; cta: string; highlight?: boolean; busy: boolean }) {
  return (
    <Card className={`flex flex-col p-5 ${highlight ? 'border-ink' : ''}`}>
      <div className="flex items-center gap-2">
        <p className="text-lg font-semibold">{name}</p>
      </div>
      <p className="mt-1 flex-1 text-sm text-muted">{blurb}</p>
      <Button className="mt-4" variant={current ? 'secondary' : highlight ? 'primary' : 'secondary'} disabled={current} loading={busy} onClick={onChoose}>
        {current ? 'Current plan' : cta}
      </Button>
    </Card>
  )
}
