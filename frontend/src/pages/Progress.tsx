import { Award, BarChart3, CalendarCheck, Flame, Share2, Wrench } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, EmptyState, LinkButton, LockCard, PageHeader, Segmented } from '../components/ui'
import { cleanRun, dayStreak, ERROR_LABELS, errorLabel, fixStreak, hasFeature, inRange, mistakeStats, topicLabel, visibleHistory } from '../lib/profile'
import { useStore } from '../lib/store'

type Range = '7' | '30' | 'all'

function upperFirst(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s
}

export function Bars({ rows, label }: { rows: { key: string; count: number; pct: number }[]; label: (k: string) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.key}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate font-medium">{upperFirst(label(r.key))}</span>
            <span className="shrink-0 tabular-nums text-muted">{r.count} · {r.pct}%</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-pen" style={{ width: `${(r.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

export default function Progress() {
  const { state } = useStore()
  const full = hasFeature(state.plan, 'full_history')
  const [range, setRange] = useState<Range>(full ? '30' : '7')
  const visible = visibleHistory(state)
  const scoped = useMemo(() => inRange(visible, range === 'all' ? null : Number(range)), [visible, range])
  const stats = useMemo(() => mistakeStats(scoped), [scoped])
  const top = stats.byType[0]
  const streak = dayStreak(state.history)
  const fixes = fixStreak(state.history)
  const run = top ? cleanRun(state.history, top.key) : 0

  if (state.history.length === 0) {
    return (
      <div>
        <PageHeader title="Your progress" subtitle="Your mistake patterns, over time" />
        <EmptyState icon={<BarChart3 className="size-6" />} title="Nothing to show yet" action={<LinkButton to="/">Check a problem</LinkButton>}>
          Every mistake you find is classified, so after a few checks you'll see exactly which kinds you make most.
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Your progress" subtitle="Your mistake patterns, over time" />

      <div className="flex items-center justify-between gap-3">
        <Segmented<Range> label="Time range" value={range} onChange={setRange} options={[
          { value: '7', label: '7 days' },
          ...(full ? [{ value: '30' as Range, label: '30 days' }, { value: 'all' as Range, label: 'All time' }] : []),
        ]} />
        {!full && <Link to="/plans" className="text-xs font-medium text-accent">Full history with Plus</Link>}
      </div>

      {top ? (
        <Card className="p-5">
          <p className="text-sm font-medium text-muted">Your most common mistake</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight">
            {top.pct}% of your mistakes{range === 'all' ? '' : ` in the last ${range} days`} are {errorLabel(top.key, true)}.
          </p>
          {hasFeature(state.plan, 'practice') ? (
            <LinkButton to={`/practice?skill=${ERROR_LABELS[top.key]?.skill ?? 'general'}`} size="sm" className="mt-4">Drill exactly that</LinkButton>
          ) : (
            <Link to="/plans" className="mt-3 inline-block text-sm font-medium text-accent">Targeted practice comes with Plus →</Link>
          )}
        </Card>
      ) : (
        <Card className="p-5">
          <p className="text-lg font-semibold">No mistakes in this period. 🎯</p>
          <p className="text-sm text-muted">{stats.problems} problem{stats.problems === 1 ? '' : 's'} checked.</p>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Stat icon={<CalendarCheck className="size-5" />} value={stats.problems} label="problems checked" />
        <Stat icon={<Wrench className="size-5" />} value={stats.fixed} label="mistakes you fixed" />
        <Stat icon={<Flame className="size-5" />} value={streak} label={`day streak`} />
        <Stat icon={<Award className="size-5" />} value={stats.allCorrect} label="all-correct problems" />
      </div>

      <Card className="p-5">
        <h2 className="mb-3 font-semibold">Streaks</h2>
        <ul className="space-y-2 text-[15px]">
          {top && <li>🧹 <span className="font-medium">{run} problem{run === 1 ? '' : 's'}</span> in a row with no {errorLabel(top.key, true)}</li>}
          <li>🔧 <span className="font-medium">{fixes} mistake{fixes === 1 ? '' : 's'}</span> in a row fixed by yourself</li>
          <li>📅 <span className="font-medium">{streak} day{streak === 1 ? '' : 's'}</span> in a row checking your work</li>
        </ul>
      </Card>

      {stats.byType.length > 0 && (
        <Card className="p-5">
          <h2 className="mb-4 font-semibold">Mistakes by type</h2>
          <Bars rows={stats.byType} label={(k) => errorLabel(k, true)} />
        </Card>
      )}
      {stats.byTopic.length > 0 && (
        <Card className="p-5">
          <h2 className="mb-4 font-semibold">Mistakes by topic</h2>
          <Bars rows={stats.byTopic} label={topicLabel} />
        </Card>
      )}

      {hasFeature(state.plan, 'sharing') ? (
        <Link to="/share">
          <Card className="flex items-center gap-3 p-4 transition hover:shadow-md">
            <Share2 className="size-5 text-accent" />
            <span className="flex-1 font-medium">Share progress with a parent or tutor</span>
          </Card>
        </Link>
      ) : (
        <LockCard compact title="Share with a parent or tutor">A link that shows patterns and progress — never photos or answers.</LockCard>
      )}
    </div>
  )
}

function Stat({ icon, value, label }: { icon: React.ReactNode; value: number; label: string }) {
  return (
    <Card className="p-4">
      <div className="mb-2 text-muted">{icon}</div>
      <p className="text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
      <p className="text-xs text-muted">{label}</p>
    </Card>
  )
}
