import { AlertTriangle, CheckCircle2, CircleDashed, CircleDot, HelpCircle, MinusCircle, XCircle } from 'lucide-react'
import type { Status, Tier } from '../lib/types'

export const STATUS_TEXT: Record<Status, string> = {
  start: 'Starting line',
  ok: 'Correct step',
  error: 'First mistake',
  warning: 'Check this step',
  follows_from_error: 'Consistent with your earlier step',
  uncertain: "Couldn't verify",
  skipped: 'Note (skipped)',
}

export function StatusIcon({ status, className = 'size-5' }: { status: Status; className?: string }) {
  switch (status) {
    case 'ok':
      return <CheckCircle2 className={`${className} text-ok`} aria-label="Correct" />
    case 'start':
      return <CircleDot className={`${className} text-muted`} aria-label="Starting line" />
    case 'error':
      return <XCircle className={`${className} text-pen`} aria-label="Mistake" />
    case 'warning':
      return <AlertTriangle className={`${className} text-warn`} aria-label="Warning" />
    case 'follows_from_error':
      return <CircleDashed className={`${className} text-faint`} aria-label="Follows from the mistake" />
    case 'uncertain':
      return <HelpCircle className={`${className} text-warn`} aria-label="Uncertain" />
    case 'skipped':
      return <MinusCircle className={`${className} text-faint`} aria-label="Skipped" />
  }
}

export function TierBadge({ tier, status }: { tier?: Tier; status: Status }) {
  if (status === 'uncertain') return <span className="whitespace-nowrap rounded-full bg-warn-soft px-2 py-0.5 text-[11px] font-medium text-warn">Uncertain</span>
  if (!tier || status === 'skipped' || status === 'start') return null
  if (tier === 'verified') return <span className="whitespace-nowrap rounded-full bg-ok-soft px-2 py-0.5 text-[11px] font-medium text-ok" title="The math engine proved this exactly">Verified</span>
  if (tier === 'numeric') return <span className="whitespace-nowrap rounded-full bg-num-soft px-2 py-0.5 text-[11px] font-medium text-num" title="Passed random-value testing; a symbolic proof timed out">Checked numerically</span>
  return <span className="whitespace-nowrap rounded-full bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-muted" title="An AI opinion the engine can't check">Unverified</span>
}

export function TierLegend() {
  return (
    <dl className="grid gap-2 text-sm sm:grid-cols-2">
      <div className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" /><div><dt className="font-medium">Verified</dt><dd className="text-muted">The math engine proved it exactly.</dd></div></div>
      <div className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 size-4 shrink-0 text-num" /><div><dt className="font-medium">Checked numerically</dt><dd className="text-muted">Passed random-value testing; a symbolic proof timed out.</dd></div></div>
      <div className="flex items-start gap-2"><HelpCircle className="mt-0.5 size-4 shrink-0 text-warn" /><div><dt className="font-medium">Uncertain</dt><dd className="text-muted">We couldn't read or verify it, so we ask instead of guessing.</dd></div></div>
      <div className="flex items-start gap-2"><CircleDashed className="mt-0.5 size-4 shrink-0 text-faint" /><div><dt className="font-medium">Unverified</dt><dd className="text-muted">An AI opinion the engine can't check (proofs, word problems).</dd></div></div>
    </dl>
  )
}
