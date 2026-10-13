import { Copy, ExternalLink, Link2, Link2Off, Share2, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ShareDashboard } from '../components/ShareDashboard'
import { Button, Card, ErrorNote, Field, inputClass, LockCard, PageHeader, useToast } from '../components/ui'
import { api } from '../lib/api'
import { hasFeature, shareSnapshot } from '../lib/profile'
import { useStore } from '../lib/store'

// In a packaged phone app the page origin isn't a web address, so share links
// use the public website address when one is configured.
const PUBLIC_URL = ((import.meta.env.VITE_PUBLIC_URL as string | undefined) ?? '').replace(/\/$/, '')

export function shareUrl(id: string): string {
  return `${PUBLIC_URL || window.location.origin}/s/${id}`
}

export default function Share() {
  const { state, dispatch } = useStore()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const plus = hasFeature(state.plan, 'sharing')
  const snap = shareSnapshot(state)

  const create = async () => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.createShare(snap)
      dispatch({ type: 'setShare', share: { id: r.id, secret: r.secret, createdAt: Date.now() } })
      toast('Share link created', 'ok')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the link')
    } finally {
      setBusy(false)
    }
  }

  const revoke = async () => {
    if (!state.share) return
    if (!window.confirm('Turn off this link? Anyone who has it will lose access.')) return
    setBusy(true)
    try {
      await api.revokeShare(state.share.id, state.share.secret)
    } catch {
      /* already gone */
    }
    dispatch({ type: 'setShare', share: null })
    setBusy(false)
    toast('Link turned off')
  }

  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
      toast('Link copied', 'ok')
    } catch {
      window.prompt('Copy this link:', url)
    }
  }

  if (!plus) {
    return (
      <div>
        <PageHeader back="/more" title="Share with a parent or tutor" />
        <LockCard title="Sharing is part of Plus">Create a link that shows patterns and progress — never photos or answers. You can turn it off any time.</LockCard>
      </div>
    )
  }

  const url = state.share ? shareUrl(state.share.id) : null

  return (
    <div className="space-y-5">
      <PageHeader back="/more" title="Share with a parent or tutor" subtitle="A link to your patterns and progress — never photos or answers." />
      {error && <ErrorNote>{error}</ErrorNote>}

      <Card className="p-5">
        <Field label="Name shown on the link" hint="A first name or nickname is plenty.">
          <input className={inputClass} value={state.settings.name} maxLength={40} placeholder="e.g. Sam"
            onChange={(e) => dispatch({ type: 'updateSettings', patch: { name: e.target.value } })} />
        </Field>
        {url ? (
          <div className="mt-5 space-y-3">
            <div className="flex items-center gap-2 rounded-2xl bg-surface-2 px-4 py-3 font-mono text-sm">
              <Link2 className="size-4 shrink-0 text-ok" />
              <span className="truncate" data-testid="share-url">{url}</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" onClick={() => copy(url)}><Copy className="size-4" /> Copy</Button>
              {'share' in navigator ? (
                <Button variant="secondary" onClick={() => navigator.share({ title: 'My math progress', url }).catch(() => {})}><Share2 className="size-4" /> Share</Button>
              ) : (
                <Link to={`/s/${state.share!.id}`} className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl border border-line bg-surface text-[15px] font-medium"><ExternalLink className="size-4" /> Preview</Link>
              )}
            </div>
            <p className="text-sm text-muted">It updates automatically as you check problems.</p>
            <Button variant="danger" className="w-full" onClick={revoke} loading={busy}><Link2Off className="size-4" /> Turn off this link</Button>
          </div>
        ) : (
          <Button size="lg" className="mt-5 w-full" onClick={create} loading={busy} data-testid="create-share"><Link2 className="size-5" /> Create a share link</Button>
        )}
      </Card>

      <div className="flex items-start gap-3 rounded-2xl bg-ok-soft/60 p-4 text-sm">
        <ShieldCheck className="mt-0.5 size-5 shrink-0 text-ok" />
        <p>Shared: mistake types, topics, streaks and practice totals. <span className="font-medium">Not shared:</span> photos, your written work, answers, your email.</p>
      </div>

      <section>
        <h2 className="mb-3 font-semibold">What they'll see</h2>
        <ShareDashboard snap={snap} />
      </section>
    </div>
  )
}
