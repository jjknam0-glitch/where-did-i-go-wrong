import { ChevronRight, Trash2, Users } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { isSnapshot, ShareDashboard } from '../components/ShareDashboard'
import { Button, Card, EmptyState, ErrorNote, inputClass, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import type { ShareSnapshot } from '../lib/profile'
import { useStore } from '../lib/store'

function idFrom(input: string): string | null {
  const s = input.trim()
  const m = s.match(/\/s\/([A-Za-z0-9_-]{6,})/)
  if (m) return m[1]
  return /^[A-Za-z0-9_-]{6,}$/.test(s) ? s : null
}

export default function Family() {
  const { state, dispatch } = useStore()
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [snaps, setSnaps] = useState<Record<string, ShareSnapshot | 'missing'>>({})

  const requested = useRef(new Set<string>())
  useEffect(() => {
    for (const f of state.family) {
      if (requested.current.has(f.id)) continue
      requested.current.add(f.id)
      api.getShare(f.id)
        .then((r) => setSnaps((s) => ({ ...s, [f.id]: isSnapshot(r.snapshot) ? r.snapshot : 'missing' })))
        .catch(() => setSnaps((s) => ({ ...s, [f.id]: 'missing' })))
    }
  }, [state.family])

  const add = async () => {
    setError(null)
    const id = idFrom(input)
    if (!id) {
      setError('Paste the share link your student sent you.')
      return
    }
    try {
      const r = await api.getShare(id)
      if (!isSnapshot(r.snapshot)) throw new Error('bad')
      requested.current.add(id)
      dispatch({ type: 'addFamily', member: { id, label: r.snapshot.name } })
      setSnaps((s) => ({ ...s, [id]: r.snapshot as ShareSnapshot }))
      setInput('')
    } catch {
      setError("That link isn't active. Ask your student to create a new one.")
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader back="/more" title="Family view" subtitle="Every student's progress in one place" />
      <Card className="p-5">
        <p className="mb-3 text-sm text-muted">Each student creates a share link (More → Share with a parent or tutor) and sends it to you.</p>
        <div className="flex gap-2">
          <input className={inputClass} value={input} onChange={(e) => setInput(e.target.value)} placeholder="Paste a share link" aria-label="Share link"
            onKeyDown={(e) => e.key === 'Enter' && add()} />
          <Button onClick={add} className="h-12 shrink-0">Add</Button>
        </div>
        {error && <div className="mt-3"><ErrorNote>{error}</ErrorNote></div>}
      </Card>

      {state.family.length === 0 ? (
        <EmptyState icon={<Users className="size-6" />} title="No students yet">Add a share link to see their patterns here. One Family plan covers several students.</EmptyState>
      ) : (
        state.family.map((f) => {
          const s = snaps[f.id]
          return (
            <section key={f.id} className="space-y-2">
              <div className="flex items-center justify-between">
                <Link to={`/s/${f.id}`} className="flex items-center gap-1 font-semibold">{s && s !== 'missing' ? s.name : f.label} <ChevronRight className="size-4 text-faint" /></Link>
                <button onClick={() => dispatch({ type: 'removeFamily', id: f.id })} className="grid size-9 place-items-center rounded-full text-faint hover:bg-surface-2 hover:text-ink" aria-label={`Remove ${f.label}`}>
                  <Trash2 className="size-4" />
                </button>
              </div>
              {s === 'missing' ? <p className="rounded-2xl bg-surface-2 p-4 text-sm text-muted">This link was turned off.</p>
                : s ? <ShareDashboard snap={s} compact /> : <p className="text-sm text-muted">Loading…</p>}
            </section>
          )
        })
      )}
    </div>
  )
}
