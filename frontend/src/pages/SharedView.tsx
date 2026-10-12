import { Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { isSnapshot, ShareDashboard } from '../components/ShareDashboard'
import { Button, EmptyState, LinkButton, PageHeader, Spinner, useToast } from '../components/ui'
import { api } from '../lib/api'
import type { ShareSnapshot } from '../lib/profile'
import { useStore } from '../lib/store'

export default function SharedView() {
  const { id } = useParams()
  const { state, dispatch } = useStore()
  const toast = useToast()
  const [snap, setSnap] = useState<ShareSnapshot | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    if (!id) return
    api.getShare(id)
      .then((r) => (isSnapshot(r.snapshot) ? setSnap(r.snapshot) : setMissing(true)))
      .catch(() => setMissing(true))
  }, [id])

  if (missing) {
    return (
      <EmptyState icon={<Users className="size-6" />} title="This link isn't active" action={<LinkButton to="/">Go to the app</LinkButton>}>
        The student may have turned it off.
      </EmptyState>
    )
  }
  if (!snap || !id) return <Spinner />
  const inFamily = state.family.some((f) => f.id === id)

  return (
    <div className="space-y-5">
      <PageHeader title={`${snap.name}'s math progress`} subtitle={`Updated ${new Date(snap.updatedAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`} />
      <ShareDashboard snap={snap} />
      <p className="text-center text-xs text-muted">Shows patterns and progress only — never photos or answers.</p>
      {!inFamily ? (
        <Button variant="secondary" className="w-full" onClick={() => { dispatch({ type: 'addFamily', member: { id, label: snap.name } }); toast(`Added ${snap.name} to your family view`, 'ok') }}>
          <Users className="size-4" /> Add to my family view
        </Button>
      ) : (
        <LinkButton to="/family" variant="secondary" className="w-full">Open family view</LinkButton>
      )}
    </div>
  )
}
