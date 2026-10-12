import { Cloud, Download, LogOut, RefreshCw, Trash2, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Card, ErrorNote, Field, inputClass, PageHeader, Segmented, Toggle, useToast } from '../components/ui'
import { api } from '../lib/api'
import { clearPhotos } from '../lib/photos'
import { syncPayload } from '../lib/state'
import { useStore } from '../lib/store'
import type { Plan } from '../lib/types'

const RANK: Record<Plan, number> = { free: 0, plus: 1, family: 2 }

export default function Account() {
  const { state, dispatch, syncNow, syncing, syncError } = useStore()
  const toast = useToast()
  const [mode, setMode] = useState<'signin' | 'signup'>('signup')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [birth, setBirth] = useState('')
  const [optIn, setOptIn] = useState(state.settings.correctionsOptIn)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const r = mode === 'signup' ? await api.signup(email, password, birth, optIn) : await api.login(email, password)
      dispatch({ type: 'setAccount', account: { token: r.token, email: r.user.email } })
      // Keep the better of the local and account plans, and save it to the account.
      const plan = RANK[r.user.plan] >= RANK[state.plan] ? r.user.plan : state.plan
      dispatch({ type: 'setPlan', plan })
      if (plan !== r.user.plan) api.updateMe(r.token, { plan }).catch(() => {})
      if (mode === 'signup') dispatch({ type: 'updateSettings', patch: { correctionsOptIn: optIn } })
      setPassword('')
      toast(mode === 'signup' ? 'Account created — your progress is saved' : 'Signed in', 'ok')
      setTimeout(() => syncNow(), 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  const signOut = async () => {
    if (state.account) await api.logout(state.account.token).catch(() => {})
    dispatch({ type: 'setAccount', account: null })
    toast('Signed out. Your progress stays on this device.')
  }

  const deleteAccount = async () => {
    if (!state.account) return
    if (!window.confirm('Delete your account and everything saved to it? Your progress on this device stays unless you clear it below.')) return
    try {
      await api.deleteMe(state.account.token)
      dispatch({ type: 'setAccount', account: null })
      toast('Account deleted')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the account')
    }
  }

  const exportData = () => {
    const blob = new Blob([JSON.stringify(syncPayload(state), null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'where-did-i-go-wrong-data.json'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const clearAll = async () => {
    if (!window.confirm('Clear all history, progress and saved photos on this device? This can’t be undone.')) return
    await clearPhotos()
    const share = state.share
    if (share) await api.revokeShare(share.id, share.secret).catch(() => {})
    dispatch({ type: 'reset' })
    toast('Everything on this device was cleared')
  }

  const setCorrections = (v: boolean) => {
    dispatch({ type: 'updateSettings', patch: { correctionsOptIn: v } })
    if (state.account) api.updateMe(state.account.token, { corrections_opt_in: v }).catch(() => {})
  }

  return (
    <div className="space-y-5">
      <PageHeader back="/more" title="Account & settings" />

      {state.account ? (
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-full bg-accent-soft text-accent"><UserRound className="size-5" /></div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{state.account.email}</p>
              <p className="text-xs text-muted">{state.lastSyncAt ? `Synced ${new Date(state.lastSyncAt).toLocaleString()}` : 'Not synced yet'}</p>
            </div>
          </div>
          {syncError && <div className="mt-3"><ErrorNote>{syncError}</ErrorNote></div>}
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button variant="secondary" onClick={syncNow} loading={syncing}><RefreshCw className="size-4" /> Sync now</Button>
            <Button variant="secondary" onClick={signOut}><LogOut className="size-4" /> Sign out</Button>
          </div>
          <button onClick={deleteAccount} className="mt-4 text-sm font-medium text-pen">Delete my account</button>
        </Card>
      ) : (
        <Card className="p-5">
          <div className="mb-4 flex items-start gap-3">
            <Cloud className="mt-0.5 size-5 text-accent" />
            <p className="text-sm text-muted">No account needed. Create one only to keep your history and mistake profile across devices. Accounts are for ages 13 and up — photos are never uploaded to your account.</p>
          </div>
          <Segmented label="Account" value={mode} onChange={setMode} options={[{ value: 'signup', label: 'Create account' }, { value: 'signin', label: 'Sign in' }]} />
          <form onSubmit={submit} className="mt-4 space-y-4">
            <Field label="Email"><input className={inputClass} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <Field label="Password" hint={mode === 'signup' ? 'At least 8 characters' : undefined}>
              <input className={inputClass} type="password" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required minLength={mode === 'signup' ? 8 : 1} value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            {mode === 'signup' && (
              <>
                <Field label="Date of birth" hint="Used once to confirm you're 13 or older. It isn't stored.">
                  <input className={inputClass} type="date" required value={birth} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setBirth(e.target.value)} />
                </Field>
                <Toggle id="optin-signup" checked={optIn} onChange={setOptIn} label="Help improve handwriting reading"
                  description="When you correct how a line was read, send that correction (text only, never the photo)." />
              </>
            )}
            {error && <ErrorNote>{error}</ErrorNote>}
            <Button type="submit" size="lg" className="w-full" loading={busy}>{mode === 'signup' ? 'Create account' : 'Sign in'}</Button>
          </form>
        </Card>
      )}

      <Card className="divide-y divide-line px-5">
        <Toggle id="optin" checked={state.settings.correctionsOptIn} onChange={setCorrections} label="Help improve handwriting reading"
          description="Share your transcription corrections (text only). Off by default." />
        <Toggle id="savephotos" checked={state.settings.savePhotos} onChange={(v) => dispatch({ type: 'updateSettings', patch: { savePhotos: v } })}
          label="Save photos to history by default" description="Kept only on this device. Otherwise photos are discarded after each check." />
        <Toggle id="metrics" checked={state.settings.showCameraMetrics} onChange={(v) => dispatch({ type: 'updateSettings', patch: { showCameraMetrics: v } })}
          label="Show camera metrics" description="Live brightness, glare, sharpness and motion numbers on the camera screen." />
      </Card>

      <Card className="divide-y divide-line px-5">
        <button onClick={exportData} className="flex w-full items-center gap-2 py-3.5 text-left text-[15px] font-medium"><Download className="size-4 text-muted" /> Download my data</button>
        <button onClick={clearAll} className="flex w-full items-center gap-2 py-3.5 text-left text-[15px] font-medium text-pen"><Trash2 className="size-4" /> Clear everything on this device</button>
      </Card>
      <p className="text-center text-xs text-muted"><Link to="/privacy" className="underline">Privacy & safety</Link></p>
    </div>
  )
}
