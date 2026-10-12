import { Eraser, Undo2 } from 'lucide-react'
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'

export interface DrawPadHandle {
  toBlob: () => Promise<Blob | null>
  isEmpty: () => boolean
}

type Stroke = { x: number; y: number }[]

/** Write with a finger or stylus. */
export const DrawPad = forwardRef<DrawPadHandle, { height?: number }>(function DrawPad({ height = 180 }, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const strokes = useRef<Stroke[]>([])
  const current = useRef<Stroke | null>(null)
  const [count, setCount] = useState(0)

  const redraw = useCallback(() => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, c.width, c.height)
    ctx.strokeStyle = '#111111'
    ctx.lineWidth = 3.2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    for (const s of [...strokes.current, ...(current.current ? [current.current] : [])]) {
      if (!s.length) continue
      ctx.beginPath()
      ctx.moveTo(s[0].x, s[0].y)
      if (s.length === 1) ctx.lineTo(s[0].x + 0.1, s[0].y + 0.1)
      for (let i = 1; i < s.length; i++) ctx.lineTo(s[i].x, s[i].y)
      ctx.stroke()
    }
  }, [])

  const resize = useCallback(() => {
    const c = canvasRef.current
    const w = wrapRef.current?.clientWidth ?? 300
    if (!c) return
    const dpr = window.devicePixelRatio || 1
    c.width = Math.round(w * dpr)
    c.height = Math.round(height * dpr)
    c.style.width = `${w}px`
    c.style.height = `${height}px`
    redraw()
  }, [height, redraw])

  useEffect(() => {
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [resize])

  useImperativeHandle(ref, () => ({
    isEmpty: () => strokes.current.length === 0,
    toBlob: () =>
      new Promise((resolve) => {
        const c = canvasRef.current
        if (!c) return resolve(null)
        c.toBlob((b) => resolve(b), 'image/png')
      }),
  }), [])

  const point = (e: React.PointerEvent) => {
    const r = canvasRef.current!.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }

  return (
    <div>
      <div ref={wrapRef} className="overflow-hidden rounded-2xl border border-line bg-white">
        <canvas
          ref={canvasRef}
          className="block touch-none"
          aria-label="Drawing area: write your corrected step"
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId)
            current.current = [point(e)]
            redraw()
          }}
          onPointerMove={(e) => {
            if (!current.current) return
            current.current.push(point(e))
            redraw()
          }}
          onPointerUp={() => {
            if (current.current) strokes.current.push(current.current)
            current.current = null
            setCount(strokes.current.length)
            redraw()
          }}
          onPointerCancel={() => {
            current.current = null
            redraw()
          }}
        />
      </div>
      <div className="mt-2 flex gap-2">
        <button type="button" className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm text-muted hover:bg-surface-2 disabled:opacity-40" disabled={!count}
          onClick={() => { strokes.current.pop(); setCount(strokes.current.length); redraw() }}>
          <Undo2 className="size-4" /> Undo
        </button>
        <button type="button" className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm text-muted hover:bg-surface-2 disabled:opacity-40" disabled={!count}
          onClick={() => { strokes.current = []; setCount(0); redraw() }}>
          <Eraser className="size-4" /> Clear
        </button>
      </div>
    </div>
  )
})
