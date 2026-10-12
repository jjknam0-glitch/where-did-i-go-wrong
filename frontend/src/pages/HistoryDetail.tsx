import { RotateCcw, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { STATUS_TEXT, StatusIcon, TierBadge } from '../components/StatusBits'
import { Tex } from '../components/Tex'
import { Badge, Button, Card, EmptyState, LinkButton, PageHeader } from '../components/ui'
import { blankDraft, newSession } from '../lib/flow'
import { deletePhoto, getPhoto } from '../lib/photos'
import { errorLabel, topicLabel, visibleHistory } from '../lib/profile'
import { useStore } from '../lib/store'
import { useRunCheck } from '../lib/useRunCheck'
import { formatDate } from './History'

export default function HistoryDetail() {
  const { id } = useParams()
  const { state, dispatch } = useStore()
  const navigate = useNavigate()
  const { run, checking, error } = useRunCheck()
  const entry = visibleHistory(state).find((h) => h.id === id)
  const [photoUrl, setPhotoUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!entry?.photoId) return
    let url: string | null = null
    let alive = true
    getPhoto(entry.photoId).then((b) => {
      if (b && alive) {
        url = URL.createObjectURL(b)
        setPhotoUrl(url)
      }
    })
    return () => {
      alive = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [entry?.photoId])

  if (!entry) {
    return <EmptyState icon={<RotateCcw className="size-6" />} title="Not found" action={<LinkButton to="/history">Back to history</LinkButton>}>This problem isn't in your history (free history shows the last 7 days).</EmptyState>
  }

  const recheck = () => {
    const drafts = entry.lines.map((l, i) => ({ ...blankDraft(i, l.math), type: l.type, latex: l.latex }))
    run(newSession({ source: entry.source === 'practice' ? 'practice' : 'typed', title: entry.title, drafts }), { isNew: true })
  }

  const remove = async () => {
    if (!window.confirm('Delete this problem from your history?')) return
    if (entry.photoId && !state.history.some((h) => h.id !== entry.id && h.photoId === entry.photoId)) await deletePhoto(entry.photoId)
    dispatch({ type: 'deleteHistory', id: entry.id })
    navigate('/history')
  }

  return (
    <div className="space-y-5">
      <PageHeader back="/history" title={entry.title ?? topicLabel(entry.topic)} subtitle={formatDate(entry.createdAt)} />
      <div className="flex flex-wrap gap-2">
        <Badge>{topicLabel(entry.topic)}</Badge>
        {entry.errors.length > 0 && <Badge tone="pen">{errorLabel(entry.errors[0].type)}</Badge>}
        {entry.fixed && <Badge tone="ok">Fixed it yourself</Badge>}
        {entry.allCorrect && <Badge tone="ok">All correct</Badge>}
        {entry.hintsUsed > 1 && <Badge>{entry.hintsUsed} hints used</Badge>}
      </div>
      {photoUrl && <img src={photoUrl} alt="Your saved photo" className="w-full rounded-3xl border border-line" />}
      <Card className="p-4">
        <ol className="space-y-3">
          {entry.lines.map((l, i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="mt-0.5 w-5 shrink-0 text-right text-sm font-semibold text-faint">{i + 1}</span>
              {l.status ? <StatusIcon status={l.status} /> : <span className="size-5" />}
              <div className="min-w-0 flex-1">
                <div className="math-scroll text-[16px]">{l.type === 'note' ? <span className="italic text-muted">{l.math}</span> : l.latex ? <Tex latex={l.latex} /> : <span className="font-mono text-sm">{l.math}</span>}</div>
                {l.status && (
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-xs text-muted">{STATUS_TEXT[l.status]}</span>
                    <TierBadge tier={l.tier} status={l.status} />
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      </Card>
      {error && <p className="text-sm text-pen">{error}</p>}
      <div className="grid grid-cols-2 gap-3">
        <Button variant="danger" size="lg" onClick={remove}><Trash2 className="size-4" /> Delete</Button>
        <Button size="lg" onClick={recheck} loading={checking}><RotateCcw className="size-4" /> Check again</Button>
      </div>
    </div>
  )
}
