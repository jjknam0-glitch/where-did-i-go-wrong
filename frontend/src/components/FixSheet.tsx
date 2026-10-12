import { Camera, Keyboard, PenLine } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { payloadFor } from '../lib/checking'
import { prepareImage } from '../lib/image'
import type { CheckLine, DraftLine, FixResponse } from '../lib/types'
import { DrawPad, type DrawPadHandle } from './DrawPad'
import { MathInput } from './MathInput'
import { TexText } from './Tex'
import { Button, ErrorNote, Segmented, Sheet } from './ui'

type Tab = 'type' | 'photo' | 'draw'

/** "Fix it yourself": rewrite just the broken step, by typing, photo or stylus. */
export function FixSheet({ open, onClose, lines, position, onFixed, transcription }: {
  open: boolean
  onClose: () => void
  lines: DraftLine[]
  position: number
  onFixed: (res: FixResponse, math: string) => void
  transcription: boolean
}) {
  const [tab, setTab] = useState<Tab>('type')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState<CheckLine | null>(null)
  const padRef = useRef<DrawPadHandle>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const initial = lines[position]?.math ?? ''
  const initialRef = useRef(initial)
  initialRef.current = initial
  // Reset only when the sheet opens (not on every parent render).
  useEffect(() => {
    if (open) {
      setText(initialRef.current)
      setError(null)
      setAttempt(null)
      setTab('type')
    }
  }, [open])

  const readImage = async (blob: Blob) => {
    setBusy(true)
    setError(null)
    try {
      const img = await prepareImage(blob, 1600)
      URL.revokeObjectURL(img.url)
      const res = await api.read(img.blob, 'line')
      if (res.source === 'manual') {
        setError("Reading handwriting isn't set up on this server — type your step instead.")
        setTab('type')
        return
      }
      const math = res.lines.map((l) => l.math).filter(Boolean).join(' ')
      if (!math) {
        setError("We couldn't read that. Try again, or type it.")
        return
      }
      setText(math)
      setTab('type') // show the reading so the student can confirm it
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reading failed.')
    } finally {
      setBusy(false)
    }
  }

  const submit = async () => {
    const math = text.trim()
    if (!math) {
      setError('Write your corrected step first.')
      return
    }
    setBusy(true)
    setError(null)
    setAttempt(null)
    try {
      const res = await api.fix(payloadFor(lines), position, math)
      if (res.valid) onFixed(res, math)
      else setAttempt(res.fix)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The check failed.')
    } finally {
      setBusy(false)
    }
  }

  const prev = position > 0 ? lines[position - 1] : null

  return (
    <Sheet open={open} onClose={onClose} title={`Fix line ${position + 1} yourself`} wide>
      {prev && (
        <p className="mb-3 text-sm text-muted">
          Start from line {position}: <span className="font-mono text-ink">{prev.math}</span>
        </p>
      )}
      <div className="mb-4">
        <Segmented<Tab> label="How to enter your fix" value={tab} onChange={setTab} options={[
          { value: 'type', label: 'Type' },
          { value: 'photo', label: 'Photo' },
          { value: 'draw', label: 'Draw' },
        ]} />
      </div>

      {tab === 'type' && (
        <div className="space-y-3">
          <MathInput label="Your corrected step" value={text} onChange={setText} onSubmit={submit} autoFocus />
        </div>
      )}
      {tab === 'photo' && (
        <div className="space-y-3 text-center">
          <p className="text-sm text-muted">Write just this step on paper and snap it.</p>
          <Button size="lg" variant="secondary" className="w-full" onClick={() => fileRef.current?.click()} loading={busy} disabled={!transcription}>
            <Camera className="size-5" /> Snap the step
          </Button>
          {!transcription && <p className="text-xs text-muted">Handwriting reading isn't set up on this server.</p>}
          <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) readImage(f) }} />
        </div>
      )}
      {tab === 'draw' && (
        <div className="space-y-3">
          <DrawPad ref={padRef} />
          <Button variant="secondary" className="w-full" loading={busy} disabled={!transcription} onClick={async () => {
            if (padRef.current?.isEmpty()) { setError('Write your step in the box first.'); return }
            const b = await padRef.current?.toBlob()
            if (b) readImage(b)
          }}>
            <PenLine className="size-4" /> Read my writing
          </Button>
          {!transcription && <p className="text-center text-xs text-muted">Handwriting reading isn't set up on this server — type it instead.</p>}
        </div>
      )}

      {error && <div className="mt-3"><ErrorNote>{error}</ErrorNote></div>}
      {attempt && (
        <div className="mt-4 rounded-2xl bg-pen-soft p-4 text-sm" role="alert">
          <p className="font-semibold text-pen">
            {attempt.status === 'uncertain' ? "We couldn't verify that one." : 'Not quite yet.'}
          </p>
          <p className="mt-1 text-ink">
            {attempt.status === 'uncertain' ? attempt.message : attempt.hints?.[1] ? <TexText text={attempt.hints[1]} /> : 'Compare it with the line before, term by term.'}
          </p>
        </div>
      )}

      {tab === 'type' && (
        <Button size="lg" className="mt-5 w-full" onClick={submit} loading={busy} data-testid="submit-fix">
          <Keyboard className="size-5" /> Check my fix
        </Button>
      )}
    </Sheet>
  )
}
