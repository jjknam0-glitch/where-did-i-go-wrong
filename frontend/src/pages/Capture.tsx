import { Flashlight, FlashlightOff, ImageUp, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ReadingOverlay } from '../components/ReadingOverlay'
import { analyzeFrame, findIssue, Guide, MESSAGES, toGray, type FrameMetrics, type Issue } from '../lib/analyzer'
import { useStore } from '../lib/store'
import { useCheckStarter } from '../lib/useCheckStarter'

const ANALYSIS_WIDTH = 320
const FRAME_MS = 166 // about 6 frames a second

type CamState = 'starting' | 'live' | 'denied' | 'unavailable' | 'captured'

export default function Capture() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const mode = params.get('mode') === 'page' ? 'page' : 'problem'
  const { state } = useStore()
  const { stage, error, setError, fromFile } = useCheckStarter()
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const prevRef = useRef<Uint8Array | null>(null)
  const guideRef = useRef(new Guide())
  const busyRef = useRef(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const [cam, setCam] = useState<CamState>('starting')
  const [message, setMessage] = useState<Issue | null>('small')
  const [progress, setProgress] = useState(0)
  const [metrics, setMetrics] = useState<FrameMetrics | null>(null)
  const [torch, setTorch] = useState<{ supported: boolean; on: boolean }>({ supported: false, on: false })
  const [flash, setFlash] = useState(0)

  const genRef = useRef(0)

  const stop = useCallback(() => {
    genRef.current++ // cancels any camera start still in flight
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  const startCamera = useCallback(async () => {
    setCam('starting')
    setError(null)
    guideRef.current.reset()
    prevRef.current = null
    busyRef.current = false
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    const gen = ++genRef.current
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      })
      if (gen !== genRef.current) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      streamRef.current = stream
      const video = videoRef.current
      if (!video) {
        stop()
        return
      }
      video.srcObject = stream
      await video.play().catch(() => {})
      const track = stream.getVideoTracks()[0]
      const caps = (track?.getCapabilities?.() ?? {}) as MediaTrackCapabilities & { torch?: boolean }
      setTorch({ supported: !!caps.torch, on: false })
      setCam('live')
    } catch (err) {
      if (gen !== genRef.current) return
      const name = (err as DOMException)?.name
      setCam(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : 'unavailable')
    }
  }, [setError, stop])

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
      setCam('unavailable')
      return
    }
    startCamera()
    return stop
  }, [startCamera, stop])

  // Stop the camera when the tab is hidden; restart when it comes back.
  useEffect(() => {
    const onVis = () => {
      if (document.hidden) stop()
      else if (cam === 'live' && !streamRef.current) startCamera()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [cam, startCamera, stop])

  const capture = useCallback(async () => {
    const video = videoRef.current
    if (!video || busyRef.current || !video.videoWidth) return
    busyRef.current = true
    // Grab a full-resolution frame from the video, not the small analysis copy.
    const c = document.createElement('canvas')
    c.width = video.videoWidth
    c.height = video.videoHeight
    const ctx = c.getContext('2d')
    if (!ctx) {
      busyRef.current = false
      return
    }
    ctx.drawImage(video, 0, 0, c.width, c.height)
    setFlash((f) => f + 1)
    try {
      navigator.vibrate?.(60)
    } catch {
      /* not supported */
    }
    const blob: Blob | null = await new Promise((resolve) => c.toBlob(resolve, 'image/jpeg', 0.92))
    if (!blob) {
      busyRef.current = false
      return
    }
    setCam('captured')
    stop()
    const ok = await fromFile(blob, mode)
    if (!ok) {
      // Let them try again.
      startCamera()
    }
  }, [fromFile, mode, startCamera, stop])

  // Frame analysis loop.
  useEffect(() => {
    if (cam !== 'live') return
    if (!canvasRef.current) canvasRef.current = document.createElement('canvas')
    const canvas = canvasRef.current
    const id = setInterval(() => {
      const video = videoRef.current
      if (!video || !video.videoWidth || busyRef.current || document.hidden) return
      const w = ANALYSIS_WIDTH
      const h = Math.max(1, Math.round((video.videoHeight / video.videoWidth) * w))
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w
        canvas.height = h
      }
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      if (!ctx) return
      ctx.drawImage(video, 0, 0, w, h)
      const gray = toGray(ctx.getImageData(0, 0, w, h).data, w, h)
      const m = analyzeFrame(gray, w, h, prevRef.current)
      prevRef.current = gray
      const result = guideRef.current.push(findIssue(m))
      setMessage(result.message)
      setProgress(result.progress)
      setMetrics(m)
      if (result.capture) capture()
    }, FRAME_MS)
    return () => clearInterval(id)
  }, [cam, capture])

  const toggleTorch = async () => {
    const track = streamRef.current?.getVideoTracks()[0]
    if (!track) return
    const on = !torch.on
    try {
      await track.applyConstraints({ advanced: [{ torch: on } as MediaTrackConstraintSet] })
      setTorch({ supported: true, on })
    } catch {
      setTorch({ supported: false, on: false })
    }
  }

  const good = progress > 0
  const ring = 2 * Math.PI * 34

  return (
    <div className="fixed inset-0 flex flex-col bg-black text-white">
      <ReadingOverlay stage={stage} />
      <video ref={videoRef} className="absolute inset-0 size-full object-cover" autoPlay playsInline muted />
      {flash > 0 && <div key={flash} className="camera-flash pointer-events-none absolute inset-0 bg-white" />}

      {/* Guide rectangle */}
      {cam === 'live' && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-8">
          <div className={`aspect-[3/4] h-[68%] max-w-full rounded-3xl border-[3px] transition-colors duration-300 ${good ? 'border-green-400 shadow-[0_0_0_9999px_rgba(0,0,0,0.25)]' : 'border-white/80 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]'}`} />
        </div>
      )}

      {/* Top bar */}
      <div className="relative z-10 flex items-center justify-between p-4 pt-[max(1rem,env(safe-area-inset-top))]">
        <button onClick={() => { stop(); navigate('/') }} className="grid size-11 place-items-center rounded-full bg-black/40 backdrop-blur" aria-label="Close camera">
          <X className="size-6" />
        </button>
        {mode === 'page' && <span className="rounded-full bg-black/40 px-3 py-1 text-xs font-medium backdrop-blur">Whole page</span>}
        {torch.supported ? (
          <button onClick={toggleTorch} className="grid size-11 place-items-center rounded-full bg-black/40 backdrop-blur" aria-label={torch.on ? 'Turn flashlight off' : 'Turn flashlight on'}>
            {torch.on ? <FlashlightOff className="size-5" /> : <Flashlight className="size-5" />}
          </button>
        ) : <span className="size-11" />}
      </div>

      {/* Coaching message */}
      {cam === 'live' && (
        <div className="relative z-10 mt-2 flex justify-center px-6" aria-live="polite">
          <span className={`rounded-full px-4 py-2 text-[15px] font-medium backdrop-blur transition ${good ? 'bg-green-500/90' : 'bg-black/55'}`}>
            {good ? 'Perfect — hold it there' : message ? MESSAGES[message] : 'Looking for your page…'}
          </span>
        </div>
      )}

      {state.settings.showCameraMetrics && metrics && cam === 'live' && (
        <pre className="absolute left-3 top-24 z-10 rounded-xl bg-black/60 p-2 font-mono text-[10px] leading-tight">
{`bright ${metrics.brightness.toFixed(0)}  glare ${(metrics.glare * 100).toFixed(1)}%
paper  ${(metrics.paperArea * 100).toFixed(0)}%  center ${metrics.offCenter.toFixed(2)}
motion ${metrics.motion.toFixed(1)}  sharp ${metrics.sharpness.toFixed(0)}
ink    ${(metrics.ink * 100).toFixed(2)}%  edge ${(metrics.inkAtEdge * 100).toFixed(0)}%`}
        </pre>
      )}

      {/* Problems with the camera itself */}
      {(cam === 'denied' || cam === 'unavailable') && (
        <div className="relative z-10 m-auto max-w-sm px-6 text-center">
          <p className="text-lg font-semibold">{cam === 'denied' ? 'Camera access is off' : 'No live camera here'}</p>
          <p className="mt-2 text-sm text-white/70">
            {cam === 'denied'
              ? 'Allow camera access in your browser settings, or upload a photo instead.'
              : window.isSecureContext ? 'Your device or browser doesn’t offer a live camera. Upload a photo instead.'
                : 'The live camera needs a secure (https) connection. Upload a photo instead.'}
          </p>
          <div className="mt-6 flex flex-col gap-3">
            <button onClick={() => fileRef.current?.click()} className="inline-flex h-14 items-center justify-center gap-2.5 rounded-2xl bg-white px-5 font-medium text-black active:scale-[0.98]"><ImageUp className="size-5" /> Upload a photo</button>
            {cam === 'denied' && <button onClick={startCamera} className="h-14 rounded-2xl border border-white/40 px-5 font-medium text-white">Try again</button>}
          </div>
        </div>
      )}

      {error && (
        <div className="relative z-10 mx-4 mt-4 rounded-2xl bg-red-600/90 px-4 py-3 text-sm" role="alert">{error}</div>
      )}

      {/* Bottom controls */}
      <div className="relative z-10 mt-auto flex items-center justify-around px-8 pb-6 pt-4">
        <button onClick={() => fileRef.current?.click()} className="grid size-12 place-items-center rounded-full bg-black/40 backdrop-blur" aria-label="Upload a photo instead">
          <ImageUp className="size-6" />
        </button>
        <button
          onClick={capture}
          disabled={cam !== 'live'}
          className="relative grid size-20 place-items-center disabled:opacity-40"
          aria-label="Take photo"
        >
          <svg className="absolute inset-0 -rotate-90" viewBox="0 0 80 80" aria-hidden>
            <circle cx="40" cy="40" r="34" fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth="5" />
            <circle cx="40" cy="40" r="34" fill="none" stroke="#4ade80" strokeWidth="5" strokeLinecap="round"
              strokeDasharray={ring} strokeDashoffset={ring * (1 - progress)} style={{ transition: 'stroke-dashoffset 160ms linear' }} />
          </svg>
          <span className="size-[60px] rounded-full bg-white" />
        </button>
        <span className="size-12" />
      </div>
      <p className="relative z-10 pb-[max(1rem,env(safe-area-inset-bottom))] text-center text-xs text-white/60">
        {cam === 'live' ? 'It snaps automatically when the photo is good' : ''}
      </p>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          e.target.value = ''
          if (f) {
            stop()
            setCam('captured')
            fromFile(f, mode).then((ok) => { if (!ok) startCamera() })
          }
        }}
      />
    </div>
  )
}
