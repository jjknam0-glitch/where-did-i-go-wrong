import { CheckCircle2, ChevronRight, Clock, Search, Wrench, XCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Tex } from '../components/Tex'
import { EmptyState, inputClass, LinkButton, LockCard, PageHeader } from '../components/ui'
import { errorLabel, FREE_HISTORY_DAYS, hasFeature, topicLabel, TOPIC_LABELS, visibleHistory } from '../lib/profile'
import { useStore } from '../lib/store'

export function formatDate(t: number): string {
  const d = new Date(t)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  const yesterday = new Date(now.getTime() - 86_400_000).toDateString() === d.toDateString()
  const time = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  if (sameDay) return `Today, ${time}`
  if (yesterday) return `Yesterday, ${time}`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: d.getFullYear() === now.getFullYear() ? undefined : 'numeric' })
}

export default function History() {
  const { state } = useStore()
  const [query, setQuery] = useState('')
  const [topic, setTopic] = useState('all')
  const visible = visibleHistory(state)
  const hidden = state.history.length - visible.length
  const topics = useMemo(() => [...new Set(state.history.map((h) => h.topic))], [state.history])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return visible.filter((h) => {
      if (topic !== 'all' && h.topic !== topic) return false
      if (!q) return true
      const hay = [topicLabel(h.topic), h.title ?? '', ...h.lines.map((l) => l.math), ...h.errors.map((e) => errorLabel(e.type))].join(' ').toLowerCase()
      return hay.includes(q)
    })
  }, [visible, query, topic])

  return (
    <div>
      <PageHeader title="History" subtitle="Every problem you've checked" />
      {state.history.length === 0 ? (
        <EmptyState icon={<Clock className="size-6" />} title="No checks yet" action={<LinkButton to="/">Check your first problem</LinkButton>}>
          Problems you check show up here, searchable by topic.
        </EmptyState>
      ) : (
        <>
          <div className="mb-4 space-y-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-faint" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search your problems" aria-label="Search history" className={`${inputClass} pl-10`} />
            </div>
            <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
              {['all', ...topics].map((t) => (
                <button key={t} onClick={() => setTopic(t)} className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition ${topic === t ? 'bg-ink text-on-ink' : 'bg-surface-2 text-muted hover:text-ink'}`}>
                  {t === 'all' ? 'All topics' : TOPIC_LABELS[t] ?? t}
                </button>
              ))}
            </div>
          </div>
          {filtered.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted">Nothing matches that search.</p>
          ) : (
            <ul className="space-y-2">
              {filtered.map((h) => {
                const first = h.lines.find((l) => l.type !== 'note')
                return (
                  <li key={h.id}>
                    <Link to={`/history/${h.id}`} className="flex items-center gap-3 rounded-2xl border border-line bg-surface p-4 transition hover:shadow-md">
                      {h.allCorrect ? <CheckCircle2 className="size-5 shrink-0 text-ok" /> : h.fixed ? <Wrench className="size-5 shrink-0 text-ok" /> : h.errors.length ? <XCircle className="size-5 shrink-0 text-pen" /> : <Clock className="size-5 shrink-0 text-faint" />}
                      <div className="min-w-0 flex-1">
                        <div className="math-scroll text-[15px]">{first ? (first.latex ? <Tex latex={first.latex} /> : <span className="font-mono text-sm">{first.math}</span>) : '—'}</div>
                        <p className="mt-0.5 truncate text-xs text-muted">
                          {topicLabel(h.topic)} · {formatDate(h.createdAt)}
                          {h.errors.length ? ` · ${errorLabel(h.errors[0].type)}${h.fixed ? ' (fixed)' : ''}` : h.allCorrect ? ' · all correct' : ''}
                        </p>
                      </div>
                      <ChevronRight className="size-4 shrink-0 text-faint" />
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
          {hidden > 0 && !hasFeature(state.plan, 'full_history') && (
            <div className="mt-6">
              <LockCard title={`${hidden} older problem${hidden === 1 ? '' : 's'} hidden`}>
                The free plan shows the last {FREE_HISTORY_DAYS} days. Plus keeps your full history.
              </LockCard>
            </div>
          )}
        </>
      )}
    </div>
  )
}
