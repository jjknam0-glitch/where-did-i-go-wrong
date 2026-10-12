import { Maximize2, Minimize2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { Status } from '../lib/types'

export interface PhotoMark {
  key: string
  quad?: [number, number][]
  box?: [number, number, number, number]
  label?: string
  status?: Status | 'pending' | 'selected' | 'fixed'
}

function quadOf(m: PhotoMark): [number, number][] | null {
  if (m.quad && m.quad.length === 4) return m.quad
  if (m.box) {
    const [l, t, r, b] = m.box
    return [[l, t], [r, t], [r, b], [l, b]]
  }
  return null
}

/** A hand-drawn-looking loop around a line of work. */
function circlePath(q: [number, number][], scale: number): { d: string; len: number } {
  const cx = q.reduce((s, p) => s + p[0], 0) / 4
  const cy = q.reduce((s, p) => s + p[1], 0) / 4
  const w = Math.hypot(q[1][0] - q[0][0], q[1][1] - q[0][1])
  const h = Math.hypot(q[3][0] - q[0][0], q[3][1] - q[0][1])
  const angle = Math.atan2(q[1][1] - q[0][1], q[1][0] - q[0][0])
  const rx = w / 2 + 18 * scale
  const ry = h / 2 + 16 * scale
  const pts: string[] = []
  const steps = 40
  // Slightly more than one turn, with a wobble, like a pen loop.
  for (let i = 0; i <= steps; i++) {
    const t = -0.35 + (i / steps) * (Math.PI * 2 + 0.55)
    const wobble = 1 + 0.035 * Math.sin(t * 3 + 1) + (i / steps) * 0.05
    const x0 = Math.cos(t) * rx * wobble
    const y0 = Math.sin(t) * ry * wobble
    const x = cx + x0 * Math.cos(angle) - y0 * Math.sin(angle)
    const y = cy + x0 * Math.sin(angle) + y0 * Math.cos(angle)
    pts.push(`${x.toFixed(1)},${y.toFixed(1)}`)
  }
  const len = Math.PI * (3 * (rx + ry) - Math.sqrt((3 * rx + ry) * (rx + 3 * ry))) * 1.12
  return { d: `M${pts[0]} L${pts.slice(1).join(' ')}`, len }
}

/** The part of the photo that holds the work, padded, so marks are easy to see. */
function focusBox(quads: [number, number][][], width: number, height: number) {
  if (!quads.length) return { x: 0, y: 0, w: width, h: height }
  const xs = quads.flat().map((p) => p[0])
  const ys = quads.flat().map((p) => p[1])
  let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys)
  const pad = Math.max(width, height) * 0.06
  x0 -= pad * 1.4; x1 += pad * 1.4; y0 -= pad; y1 += pad
  // Not too wide and flat: keep at least a 0.45 height/width ratio.
  const minH = (x1 - x0) * 0.45
  if (y1 - y0 < minH) {
    const extra = (minH - (y1 - y0)) / 2
    y0 -= extra
    y1 += extra
  }
  x0 = Math.max(0, x0); y0 = Math.max(0, y0); x1 = Math.min(width, x1); y1 = Math.min(height, y1)
  if (x1 - x0 < width * 0.2 || y1 - y0 < height * 0.08) return { x: 0, y: 0, w: width, h: height }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }
}

export function PhotoView({ src, width, height, marks = [], circle, className = '' }:
  { src: string; width: number; height: number; marks?: PhotoMark[]; circle?: PhotoMark | null; className?: string }) {
  const [whole, setWhole] = useState(false)
  const view = useMemo(() => {
    const quads = [...marks, ...(circle ? [circle] : [])].map(quadOf).filter((q): q is [number, number][] => !!q)
    return focusBox(quads, width, height)
  }, [marks, circle, width, height])
  const cropped = view.w < width * 0.97 || view.h < height * 0.97
  const vb = whole || !cropped ? { x: 0, y: 0, w: width, h: height } : view
  // Marks are sized relative to what's on screen, so they look the same zoomed in or out.
  const scale = Math.max(vb.w, vb.h) / 1000
  const ring = useMemo(() => {
    const q = circle ? quadOf(circle) : null
    return q ? circlePath(q, scale) : null
  }, [circle, scale])

  return (
    <div className={`relative overflow-hidden rounded-3xl border border-line bg-surface-2 ${className}`}>
      <svg className="block h-auto w-full" viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} role="img" aria-label="Your work">
        <image href={src} x={0} y={0} width={width} height={height} preserveAspectRatio="none" />
        {marks.map((m) => {
          const q = quadOf(m)
          if (!q) return null
          const color =
            m.status === 'ok' || m.status === 'start' ? 'var(--ok)'
              : m.status === 'fixed' ? 'var(--accent)'
                : m.status === 'error' ? 'var(--pen)'
                  : m.status === 'warning' || m.status === 'uncertain' || m.status === 'pending' ? 'var(--warn)'
                    : m.status === 'selected' ? 'var(--accent)' : 'rgba(255,255,255,0.0)'
          const showBox = m.status === 'pending' || m.status === 'selected' || m.status === 'uncertain' || m.status === 'warning'
          const rx = Math.min(Math.max(q[1][0], q[2][0]) + 10 * scale, vb.x + vb.w - 32 * scale)
          const ry = (q[1][1] + q[2][1]) / 2
          const lx = Math.max(Math.min(q[0][0], q[3][0]) - 20 * scale, vb.x + 16 * scale)
          const check = m.status === 'ok' || m.status === 'start' || m.status === 'fixed'
          return (
            <g key={m.key}>
              {showBox && (
                <polygon points={q.map((p) => p.join(',')).join(' ')} fill="none" stroke={color} strokeWidth={3 * scale}
                  strokeDasharray={m.status === 'pending' ? `${10 * scale} ${7 * scale}` : undefined} />
              )}
              {check && (
                <g className="pop-in" style={{ transformOrigin: `${rx + 14 * scale}px ${ry}px` }}>
                  <circle cx={rx + 14 * scale} cy={ry} r={15 * scale} fill={color} />
                  {m.status === 'fixed' ? (
                    <path d={`M${rx + 8 * scale},${ry + 6 * scale} l${3 * scale},${-1 * scale} l${8 * scale},${-8 * scale} l${-2 * scale},${-2 * scale} l${-8 * scale},${8 * scale} z`} fill="white" />
                  ) : (
                    <path d={`M${rx + 7 * scale},${ry} l${5 * scale},${5 * scale} l${9 * scale},${-10 * scale}`} fill="none" stroke="white" strokeWidth={3.2 * scale} strokeLinecap="round" strokeLinejoin="round" />
                  )}
                </g>
              )}
              {m.label && (
                <g>
                  <circle cx={lx} cy={(q[0][1] + q[3][1]) / 2} r={14 * scale} fill={showBox ? color : 'rgba(0,0,0,0.55)'} />
                  <text x={lx} y={(q[0][1] + q[3][1]) / 2 + 5 * scale} textAnchor="middle" fontSize={15 * scale} fontWeight={700} fill="white">{m.label}</text>
                </g>
              )}
            </g>
          )
        })}
        {ring && (
          <path d={ring.d} fill="none" stroke="var(--pen)" strokeWidth={6 * scale} strokeLinecap="round" strokeLinejoin="round"
            className="pen-stroke" style={{ ['--len' as string]: ring.len.toFixed(0) }} />
        )}
      </svg>
      {cropped && (
        <button onClick={() => setWhole((w) => !w)} className="absolute bottom-2 right-2 flex items-center gap-1 rounded-full bg-black/55 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
          {whole ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />} {whole ? 'Zoom to work' : 'Whole photo'}
        </button>
      )}
    </div>
  )
}
