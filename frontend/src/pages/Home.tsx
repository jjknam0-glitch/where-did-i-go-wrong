import { ArrowRight, Camera, FileText, ImageUp, Layers, Lock, PencilLine, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ReadingOverlay } from '../components/ReadingOverlay'
import { Badge, Button, Card, ErrorNote } from '../components/ui'
import { api, apiUrl } from '../lib/api'
import { checksLeftToday, dayStreak, errorLabel, FREE_CHECKS_PER_DAY, hasFeature, mistakeStats, visibleHistory } from '../lib/profile'
import { useStore } from '../lib/store'
import type { Sample } from '../lib/types'
import { cameraSupported, useCheckStarter } from '../lib/useCheckStarter'
import { useHealth } from '../lib/useHealth'

export default function Home() {
  const { state } = useStore()
  const navigate = useNavigate()
  const { health, error: healthError } = useHealth()
  const { stage, error, fromFile, fromSample } = useCheckStarter()
  const [samples, setSamples] = useState<Sample[]>([])
  const [pageMode, setPageMode] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const canPage = hasFeature(state.plan, 'page_mode')
  const left = checksLeftToday(state)
  const camera = cameraSupported()

  useEffect(() => {
    api.samples().then(setSamples).catch(() => setSamples([]))
  }, [])

  const recent = visibleHistory(state)
  const stats = mistakeStats(recent)
  const streak = dayStreak(state.history)
  const top = stats.byType[0]

  return (
    <div className="space-y-8">
      <ReadingOverlay stage={stage} />

      <section className="pt-2">
        <h1 className="text-[34px] font-semibold leading-[1.08] tracking-tight sm:text-[40px]">
          Find the exact line where your math <span className="relative whitespace-nowrap">went wrong
            <svg className="absolute -inset-x-2 -inset-y-1.5 h-[calc(100%+12px)] w-[calc(100%+16px)]" viewBox="0 0 200 60" preserveAspectRatio="none" aria-hidden>
              <path d="M10 32 C 12 8, 188 4, 192 28 C 196 52, 20 58, 8 36" fill="none" className="stroke-pen" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </span>.
        </h1>
        <p className="mt-4 text-[17px] leading-relaxed text-muted">
          Snap your handwritten work. We circle the first broken step, give you a hint, and let you fix it yourself.
        </p>
      </section>

      <section className="space-y-3">
        {error && <ErrorNote>{error}</ErrorNote>}
        {healthError && <ErrorNote>Can't reach the server right now. Typing your work still needs the server, so try again in a moment.</ErrorNote>}
        {health && !health.transcription && (
          <div className="rounded-2xl border border-line bg-surface px-4 py-3 text-sm text-muted">
            Handwriting reading isn't set up on this server yet, so after a photo you'll type each line yourself. The samples below work fully.
          </div>
        )}

        {camera && (
          <Button size="lg" className="w-full" onClick={() => navigate(pageMode && canPage ? '/capture?mode=page' : '/capture')}>
            <Camera className="size-5" /> Snap your work
          </Button>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Button variant={camera ? 'secondary' : 'primary'} size="lg" className={camera ? '' : 'col-span-2'} onClick={() => fileRef.current?.click()}>
            <ImageUp className="size-5" /> Upload
          </Button>
          <Button variant="secondary" size="lg" className={camera ? '' : 'col-span-2'} onClick={() => navigate('/type')}>
            <PencilLine className="size-5" /> Type it
          </Button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          // Without a live camera this is the fallback, so open the camera directly on phones.
          {...(camera ? {} : { capture: 'environment' as const })}
          className="hidden"
          data-testid="upload-input"
          onChange={(e) => {
            const f = e.target.files?.[0]
            e.target.value = ''
            if (f) fromFile(f, pageMode && canPage ? 'page' : 'problem')
          }}
        />

        <div className="flex items-center justify-between gap-3 rounded-2xl bg-surface-2/70 px-4 py-3">
          <label className="flex items-center gap-3 text-sm">
            <Layers className="size-4 text-muted" />
            <span>
              <span className="font-medium">Whole-page mode</span>
              <span className="block text-xs text-muted">A report for every problem on the page</span>
            </span>
          </label>
          {canPage ? (
            <input type="checkbox" aria-label="Whole-page mode" className="size-5 accent-[var(--ink)]" checked={pageMode} onChange={(e) => setPageMode(e.target.checked)} />
          ) : (
            <Link to="/plans" className="flex items-center gap-1 text-xs font-medium text-accent"><Lock className="size-3.5" /> Plus</Link>
          )}
        </div>

        {left !== Infinity && (
          <p className="text-center text-xs text-muted">
            {left > 0 ? `${left} of ${FREE_CHECKS_PER_DAY} free checks left today` : 'You’ve used today’s free checks.'}{' '}
            <Link to="/plans" className="font-medium text-accent">Unlimited with Plus</Link>
          </p>
        )}
      </section>

      {samples.length > 0 && (
        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">Try a sample</h2>
            <span className="text-xs text-muted">Sample photos with rendered handwriting</span>
          </div>
          <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2">
            {samples.map((s) => (
              <button
                key={s.id}
                onClick={() => fromSample(s.id, s.title)}
                className="w-40 shrink-0 snap-start overflow-hidden rounded-2xl border border-line bg-surface text-left transition hover:shadow-md active:scale-[0.98]"
                data-testid={`sample-${s.id}`}
              >
                <img src={apiUrl(s.image)} alt="" loading="lazy" className="aspect-[4/5] w-full bg-surface-2 object-cover" />
                <div className="p-3">
                  <p className="text-sm font-medium leading-snug">{s.title}</p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted">{s.description}</p>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {recent.length > 0 && (
        <section>
          <Link to="/progress">
            <Card className="flex items-center gap-4 p-4 transition hover:shadow-md">
              <div className="grid size-11 place-items-center rounded-2xl bg-accent-soft text-accent">
                <Sparkles className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {top ? `${top.pct}% of your recent mistakes are ${errorLabel(top.key, true)}` : 'No mistakes caught lately — nice work'}
                </p>
                <p className="text-sm text-muted">
                  {stats.problems} problem{stats.problems === 1 ? '' : 's'} checked{streak > 1 ? ` · ${streak}-day streak` : ''}
                </p>
              </div>
              <ArrowRight className="size-5 text-faint" />
            </Card>
          </Link>
        </section>
      )}

      <section>
        <Card className="p-5">
          <div className="mb-4 flex items-center gap-2">
            <Badge tone="ok">How it stays honest</Badge>
          </div>
          <p className="text-[15px] leading-relaxed">
            <span className="font-semibold">The AI reads your handwriting. A math engine judges it.</span>{' '}
            <span className="text-muted">Every verdict is proven by a computer algebra system, and when we're unsure we ask instead of guessing.</span>
          </p>
          <ol className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
            {[
              ['1', 'Snap', 'Live guidance helps you take a sharp, even photo.'],
              ['2', 'Confirm', 'Check that we read each line right — one tap if unsure.'],
              ['3', 'Fix it', 'See the first broken step, climb the hints, rewrite it.'],
            ].map(([n, t, d]) => (
              <li key={n} className="rounded-2xl bg-surface-2/70 p-3">
                <span className="text-xs font-semibold text-faint">{n}</span>
                <p className="font-medium">{t}</p>
                <p className="mt-0.5 text-muted">{d}</p>
              </li>
            ))}
          </ol>
          <Link to="/how-it-works" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent">
            <FileText className="size-4" /> How it works <ArrowRight className="size-4" />
          </Link>
        </Card>
      </section>
    </div>
  )
}
