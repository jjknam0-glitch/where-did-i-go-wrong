import { CalendarDays, CheckCircle2, ShieldCheck, Target, Wrench, XCircle } from 'lucide-react'
import type { ShareSnapshot } from '../lib/profile'
import { errorLabel, topicLabel } from '../lib/profile'
import { Bars, Row } from './Stats'
import { Card } from './ui'

export function isSnapshot(v: unknown): v is ShareSnapshot {
  const s = v as ShareSnapshot
  return !!s && typeof s === 'object' && typeof s.name === 'string' && !!s.month && Array.isArray(s.month.byType)
}

/** What a parent or tutor sees: patterns and progress, never photos or answers. */
export function ShareDashboard({ snap, compact = false }: { snap: ShareSnapshot; compact?: boolean }) {
  const top = snap.month.byType[0]
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <p className="text-sm text-muted">Last 30 days</p>
        <p className="mt-1 text-xl font-semibold tracking-tight">
          {top ? `${top.pct}% of ${snap.name}'s mistakes are ${errorLabel(top.key, true)}.` : `${snap.name} hasn't made any classified mistakes lately.`}
        </p>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <Mini value={snap.month.problems} label="problems" />
          <Mini value={snap.month.fixed} label="fixed alone" />
          <Mini value={snap.streaks.days} label="day streak" />
        </div>
      </Card>
      {!compact && (
        <>
          {snap.month.byType.length > 0 && (
            <Card className="p-5">
              <h3 className="mb-4 font-semibold">Mistakes by type</h3>
              <Bars rows={snap.month.byType} label={(k) => errorLabel(k, true)} />
            </Card>
          )}
          {snap.month.byTopic.length > 0 && (
            <Card className="p-5">
              <h3 className="mb-4 font-semibold">By topic</h3>
              <Bars rows={snap.month.byTopic} label={topicLabel} />
            </Card>
          )}
          <Card className="p-5">
            <h3 className="mb-3 font-semibold">Progress</h3>
            <ul className="space-y-2.5 text-[15px]">
              {snap.streaks.cleanRun && <Row icon={<ShieldCheck className="size-4" />}>{snap.streaks.cleanRun.count} problems in a row with no {errorLabel(snap.streaks.cleanRun.type, true)}</Row>}
              <Row icon={<Wrench className="size-4" />}>{snap.streaks.fixes} mistakes in a row fixed without an answer key</Row>
              <Row icon={<Target className="size-4" />}>{snap.practice.correct} of {snap.practice.sessions} practice problems right this month</Row>
              <Row icon={<CalendarDays className="size-4" />}>{snap.allTime.problems} problems checked in total</Row>
            </ul>
          </Card>
          {snap.recent.length > 0 && (
            <Card className="p-5">
              <h3 className="mb-3 font-semibold">Recent problems</h3>
              <ul className="space-y-2">
                {snap.recent.map((r, i) => (
                  <li key={i} className="flex items-center gap-3 text-sm">
                    {r.allCorrect ? <CheckCircle2 className="size-4 text-ok" /> : r.fixed ? <Wrench className="size-4 text-ok" /> : r.error ? <XCircle className="size-4 text-pen" /> : <span className="size-4" />}
                    <span className="flex-1">{topicLabel(r.topic)}{r.error ? ` — ${errorLabel(r.error)}${r.fixed ? ', fixed' : ''}` : r.allCorrect ? ' — all correct' : ''}</span>
                    <span className="text-xs text-muted">{new Date(r.at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

function Mini({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-2xl bg-surface-2/70 py-3">
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      <p className="text-[11px] text-muted">{label}</p>
    </div>
  )
}
