import { describe, expect, it } from 'vitest'
import { analyzeFrame, findIssue, Guide, THRESHOLDS } from './analyzer'

const W = 320
const H = 240

/** A synthetic frame: dark desk, optional paper rectangle with "writing" strokes. */
function frame(opts: { desk?: number; paper?: [number, number, number, number] | null; paperLevel?: number; ink?: boolean; hotspot?: boolean; blur?: boolean; inkAt?: 'edge' | 'middle' } = {}) {
  const { desk = 50, paper = [60, 40, 260, 200], paperLevel = 215, ink = true, hotspot = false, inkAt = 'middle' } = opts
  const g = new Uint8Array(W * H).fill(desk)
  if (paper) {
    const [x0, y0, x1, y1] = paper
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) g[y * W + x] = paperLevel
    if (ink) {
      // crisp 2px strokes in rows
      const rows = inkAt === 'edge' ? [y0 + 2, y0 + 3] : [y0 + 40, y0 + 41, y0 + 70, y0 + 71, y0 + 100, y0 + 101]
      for (const y of rows) for (let x = x0 + 20; x < x1 - 20; x += 3) { g[y * W + x] = 30; g[y * W + x + 1] = 30 }
    }
    if (hotspot) for (let y = y0 + 10; y < y0 + 80; y++) for (let x = x0 + 10; x < x0 + 120; x++) g[y * W + x] = 255
  }
  if (opts.blur) {
    const out = new Uint8Array(g)
    for (let pass = 0; pass < 4; pass++) {
      for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
        const p = y * W + x
        out[p] = (g[p] + g[p - 1] + g[p + 1] + g[p - W] + g[p + W]) / 5
      }
      g.set(out)
    }
  }
  return g
}

describe('frame analysis', () => {
  it('accepts a good frame', () => {
    const m = analyzeFrame(frame(), W, H, frame())
    expect(findIssue(m)).toBeNull()
  })
  it('too dark', () => {
    const m = analyzeFrame(frame({ desk: 10, paperLevel: 45 }), W, H, null)
    expect(findIssue(m)).toBe('dark')
  })
  it('paper too small', () => {
    const m = analyzeFrame(frame({ paper: [140, 100, 180, 140] }), W, H, null)
    expect(findIssue(m)).toBe('small')
  })
  it('glare is a hotspot, not bright paper', () => {
    expect(findIssue(analyzeFrame(frame({ hotspot: true, paperLevel: 200 }), W, H, null))).toBe('glare')
    expect(findIssue(analyzeFrame(frame({ paperLevel: 255 }), W, H, frame({ paperLevel: 255 })))).toBeNull()
  })
  it('off centre', () => {
    const m = analyzeFrame(frame({ paper: [150, 100, 319, 239] }), W, H, null)
    expect(['offcenter', 'cutoff']).toContain(findIssue(m))
  })
  it('motion', () => {
    const a = frame()
    const b = frame({ paper: [80, 60, 280, 220] })
    const m = analyzeFrame(b, W, H, a)
    expect(m.motion).toBeGreaterThan(THRESHOLDS.maxMotion)
    expect(findIssue(m)).toBe('moving')
  })
  it('blur', () => {
    const m = analyzeFrame(frame({ blur: true }), W, H, frame({ blur: true }))
    expect(m.sharpness).toBeLessThan(analyzeFrame(frame(), W, H, null).sharpness)
    expect(findIssue(m)).toBe('blurry')
  })
  it('no writing', () => {
    const f = frame({ ink: false })
    expect(findIssue(analyzeFrame(f, W, H, f))).toBe('nowriting')
  })
  it('writing cut off at the frame edge', () => {
    const f = frame({ paper: [40, 0, 280, 230], inkAt: 'edge' })
    expect(findIssue(analyzeFrame(f, W, H, f))).toBe('cutoff')
  })
})

describe('guide (no flicker, auto-capture)', () => {
  it('changes the message only after 3 frames in a row', () => {
    const g = new Guide()
    expect(g.push('dark').message).toBe('small')
    expect(g.push('dark').message).toBe('small')
    expect(g.push('dark').message).toBe('dark')
    expect(g.push('glare').message).toBe('dark')
  })
  it('captures after 6 good frames in a row', () => {
    const g = new Guide()
    for (let i = 0; i < 5; i++) expect(g.push(null).capture).toBe(false)
    expect(g.push(null).capture).toBe(true)
    g.reset()
    for (let i = 0; i < 5; i++) g.push(null)
    expect(g.push('moving').capture).toBe(false)
    expect(g.goodRun).toBe(0)
  })
})
